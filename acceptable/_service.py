# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).

"""acceptable - version Flask views using the Accept header."""
import functools
import re

from flask import request
from werkzeug.exceptions import NotAcceptable


class AcceptableService:

    """Main entry point for a service using acceptable to manage API versions.

    This class manages service-wide options such as the vendor identifier. An
    instance of this class is required to create an API endpoint.
    """

    def __init__(self, vendor, flask_app=None):
        """Create an instance of AcceptableService.

        :param vendor: The vendor string. Must not contain spaces or
            punctuation.
        :param flask_app: an instance of flask.Flask. If not specified, the
            'initialise' method must be called before any of the API endpoints
            will be registered in the Flask URL route.
        :raises ValueError: If the vendor string contains spaces or
            punctuation.
        :raises TypeError: If the vendor string is something other than a
            string.
        """
        if not isinstance(vendor, str):
            raise TypeError(
                "vendor must be a string, not %s" % type(vendor).__name__)
        if not vendor.isalpha():
            raise ValueError("vendor identifier must consist of alphanumeric "
                             "characters only.")
        self.vendor = vendor
        self._flask_app = flask_app
        self._late_registrations = []
        self._completed_registrations = []

    def api(self, url, name, **options):
        """Add an API to the service.

        :param url: This is the url that the API should be registered at.
        :param name: This is the name the URL route should be registered in
            flask with.

        Other keyword arguments may be used, and they will be passed to the
        underlying flask application. Of particular interest is the 'methods'
        keyword argument, which can be used to specify the HTTP method the URL
        will be added for.
        """
        used_names = [
            i[1] for i in
            self._late_registrations + self._completed_registrations]
        if name in used_names:
            raise ValueError(
                "The name '%s' has already been registered for an API."
                % name)
        api = AcceptableAPI(self)
        if self._flask_app is None:
            self._late_registrations.append((url, name, api, options))
        else:
            self._flask_app.add_url_rule(url, name, view_func=api, **options)
            self._completed_registrations.append((url, name, api, options))
        return api

    def initialise(self, flask_app):
        """Initialise the API.

        This method initialises the API (for the cases where no flask
        application was passed to AcceptableService.__init__) or
        re-initialises the API (for the case where you want to bind the API
        to a new/different flask application). In the latter case the old
        flask application will still be bound to the API views - it is the
        callers responsibility to destroy it.

        """
        if flask_app == self._flask_app:
            return  # already initialised to this flask application.
        if self._flask_app is not None:
            # we're re-binding the API to a new flask app. Iterate over the
            # already completed registrations for the current app. There should
            # never be late registrations left at this point:
            assert self._late_registrations == [], "Late registrations should \
                not exist when rebinding API to a new flask application!"
            api_views_to_register = self._completed_registrations
        else:
            # This is the first (late) initialisation, binding to a new flask
            # application. Completed registrations should be empty at this
            # point:
            assert self._completed_registrations == [], "Completed \
                registrations should be empty when binding to the first flask \
                application!"
            api_views_to_register = self._late_registrations
        self._flask_app = flask_app
        completed_registrations = []
        while api_views_to_register:
            url, name, api, options = api_views_to_register.pop()
            self._flask_app.add_url_rule(url, name, view_func=api, **options)
            completed_registrations.append((url, name, api, options))
        self._completed_registrations = completed_registrations


class AcceptableAPI:

    def __init__(self, service):
        self.endpoint_map = EndpointMap()
        self.service = service

    def __call__(self, *args, **kwargs):
        # find the correct version / tagged view and call it.
        version, flag = parse_accept_headers(
            self.service.vendor, request.accept_mimetypes.values())
        if version is None:
            version = EndpointMap.DefaultView
        view = self.endpoint_map.get_view(version, flag)
        if view:
            return view(*args, **kwargs)
        else:
            description = "Could not find view for version '%s'" % version
            if flag is not None:
                description += " and flag '%s'" % flag
            raise NotAcceptable(description)

    def view(self, introduced_at, flag=None):
        assert isinstance(introduced_at, str)
        assert isinstance(flag, (str, type(None)))

        def wrapper(fn):
            self.register_view(introduced_at, flag, fn)

            @functools.wraps(fn)
            def indirection(*args, **kwargs):
                return self(*args, **kwargs)
            return indirection
        return wrapper

    def register_view(self, introduced_at, flag, view_fn):
        assert isinstance(introduced_at, str)
        assert isinstance(flag, (str, type(None)))
        self.endpoint_map.add_view(introduced_at, flag, view_fn)


def parse_accept_headers(vendor, header_values):
    """Parse the Accept header values, returning the client's requested API
    version and API flag, if any.

    :param vendor: The vendor identifier for the current service.
    :param header_values: A list of header values to inspect.
    Returns a 2-tuple of version, tag.

    If the client requested no tag, the second parameter will be None.
    If the client does not specify a version, or the version is poorly
        formatted this function will return (None, None)
    """
    for accept_value in header_values:
        m = re.match(
            r'application/vnd.%s.(\d+\.\d+)(\+?.*)' % vendor,
            accept_value
        )
        if m:
            version, tags = m.groups()
            tags = tags.lstrip('+') if tags else None
            return (version, tags)
    return None, None


class EndpointMap:

    """Keep track of which views have been registered, and select an
    appropriate view based on a client's request.

    Each view is selected based on three attributes:
     * The flag the view requires.
     * The version the view was added in.

    Of these three attributes, the first two are matched literally, but the
    third is slightly more complex: a view added in '1.0' is still available
    in '1.1' even if it wasn't registered at that version.

    This class attaches no checks to the 'view' objects that it stores: It only
    applies semantic meaning to the 'keys' listed above.
    """

    # The DefaultView sentinel represents whatever is the default version of
    # a view:
    DefaultView = object()

    def __init__(self):
        self._map = {}

    def add_view(self, version, flag, view):
        _check_version_and_flag_types(version, flag)

        if flag not in self._map:
            self._map[flag] = {version: view}
        else:
            self._map[flag][version] = view

    def get_view(self, version, flag=None):
        _check_version_and_flag_types(version, flag)

        versionmap = self._map.get(flag, {})
        # An exact match is easy:
        if version == EndpointMap.DefaultView:
            latest_version = sorted(versionmap.keys(), reverse=True)[0]
            return versionmap[latest_version]
        if version in versionmap:
            return versionmap[version]
        # no exact match found, iterate over available versions
        # until a view is found that's lower than the requested
        # version.
        for available_version in sorted(versionmap.keys(), reverse=True):
            if available_version < version:
                return versionmap[available_version]
        # If we can't find a view with the flagt present, consider views
        # without the view as a fallback:
        if flag is not None:
            return self.get_view(version, flag=None)
        # Client perhaps asked for an older version than we have
        # in our map - return None:
        return None


def _check_version_and_flag_types(version, flag):
    if not isinstance(flag, (str, type(None))):
        raise TypeError(
            "Flag must be a string or None, not %s" % type(flag).__name__)
    if version != EndpointMap.DefaultView:
        if not isinstance(version, str):
            raise TypeError(
                "Version must be a string, not %s" % type(version).__name__)
        try:
            major, minor = version.split('.')
        except ValueError:
            raise ValueError("Version must be in the format <major>.<minor>")
        else:
            if not major.isdecimal():
                raise ValueError("Major version number is not an integer.")
            if not minor.isdecimal():
                raise ValueError("Minor version number is not an integer.")
