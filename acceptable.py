# -*- coding: utf-8 -*-
# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).

"""acceptable - version Flask views using the Accept header."""

import re

from flask import request
from werkzeug.exceptions import NotAcceptable


class AcceptableService:

    """Main entry point for a service using acceptable to manage API versions.

    This class manages service-wide options such as the vendor identifier. An
    instance of this class is required to create an API endpoint.
    """

    def __init__(self, vendor, flask_app):
        """Create an instance of AcceptableService.

        :param vendor: The vendor string. Must not contain spaces or
            punctuation.
        :param flask_app: an instance of flask.Flask.
        """
        self.vendor = vendor
        self._flask_app = flask_app

    def api(self, url, **options):
        """Add a URL endpoint.

        The 'url' parameter is passed to the Flask.add_url_rule method. Other
        keyword arguments may be used, and they will be passed to the
        underlying flask application.
        """
        api = AcceptableAPI(self)
        name = '%s.%s' % (self.vendor, url)
        self._flask_app.add_url_rule(url, name, view_func=api, **options)
        return api


class AcceptableAPI:

    def __init__(self, service):
        self.endpoint_map = EndpointMap()
        self.service = service

    def __call__(self, *args, **kwargs):
        # find the correct version / tagged view and call it.
        version, flag = parse_accept_headers(
            self.service.vendor, request.accept_mimetypes.values())
        view = self.endpoint_map.get_view(version, flag)
        if view:
            return view(*args, **kwargs)
        else:
            raise NotAcceptable(
                "Could not find view for version %s and tags %r" %
                (version, flag))

    def view(self, introduced_at, flag=None):
        assert isinstance(introduced_at, str)
        assert isinstance(flag, str)

        def wrapper(fn):
            self.endpoint_map.add_view(introduced_at, flag, fn)
        return wrapper


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
        if version in versionmap:
            return versionmap[version]
        # no exact match found, iterate over available versions
        # until a view is found that's lower than the requested
        # version.
        for available_version in sorted(versionmap.keys()):
            if available_version > version:
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
