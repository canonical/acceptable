# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).

"""acceptable - Programatic API Metadata for Flask apps."""
from collections import OrderedDict
import textwrap

from acceptable import _validation
from acceptable.util import get_callsite_location


class InvalidAPI(Exception):
    pass


class APIMetadata:
    """Global datastructure for all services.

    Provides a single point to register apis against, so we can easily inspect
    and verify uniqueness.
    """

    def __init__(self):
        self.services = {}
        self.api_names = set()
        self.urls = set()
        self._current_version = None

    def register_service(self, name, group):
        if (name, group) not in self.services:
            self.services[name, group] = {}

    def register_api(self, name, group, api):
        if api.name in self.api_names:
            raise InvalidAPI(
                'API {} is already registered in service {}'.format(
                    api.name, name)
            )
        url_key = (api.url, tuple(api.methods))
        if url_key in self.urls:
            raise InvalidAPI(
                'URL {} {} is already in service {}'.format(
                    '|'.join(api.methods), api.url, name)
            )
        self.api_names.add(api.name)
        self.urls.add(url_key)
        self.services[name, group][api.name] = api

    @property
    def current_version(self):
        if self._current_version is None:
            versions = set()
            for service in self.services.values():
                for api in service.values():
                    versions.add(api.introduced_at)
                    if api._changelog:
                        versions.add(max(api._changelog))
            if versions:
                self._current_version = max(versions)
        return self._current_version

    def bind(self, flask_app, name, group=None):
        """Bind the service API urls to a flask app."""
        for name, api in self.services[name, group].items():
            # only bind APIs that have views associated with them
            if api.view_fn is None:
                continue
            if name not in flask_app.view_functions:
                flask_app.add_url_rule(
                    api.url, name, view_func=api.view_fn, **api.options)

    def bind_all(self, flask_app):
        for name, group in self.services:
            self.bind(flask_app, name, group)

    def clear(self):
        self.services.clear()
        self.api_names.clear()
        self.urls.clear()
        self._current_version = None


Metadata = APIMetadata()


class AcceptableService:
    """User facing API for a service using acceptable to manage API versions.

    This provides a nicer interface to manage the global API metadata within
    a single file.

    It is just a factory and proxy to the global metadata state, it does not
    store any API state internally.
    """

    def __init__(self, name, group=None, metadata=Metadata):
        """Create an instance of AcceptableService.

        :param name: The service name.
        :param group: An arbitrary API group within a service.
        :raises TypeError: If the name string is something other than a
            string.
        """
        if not isinstance(name, str):
            raise TypeError(
                "name must be a string, not %s" % type(name).__name__)
        self.name = name
        self.group = group
        self.metadata = metadata
        self.metadata.register_service(name, group)
        self.location = get_callsite_location()

    @property
    def apis(self):
        return self.metadata.services[self.name, self.group]

    def api(self, url, name, introduced_at=None, **options):
        """Add an API to the service.

        :param url: This is the url that the API should be registered at.
        :param name: This is the name of the api, and will be registered with
            flask apps under.

        Other keyword arguments may be used, and they will be passed to the
        flask application when initialised. Of particular interest is the
        'methods' keyword argument, which can be used to specify the HTTP
        method the URL will be added for.
        """
        location = get_callsite_location()
        api = AcceptableAPI(
            name, url, introduced_at, options, location=location)
        self.metadata.register_api(self.name, self.group, api)
        return api

    def bind(self, flask_app):
        """Bind the service API urls to a flask app."""
        self.metadata.bind(flask_app, self.name, self.group)

    # b/w compat
    initialise = bind


class AcceptableAPI:
    """Metadata abount an api endpoint."""

    def __init__(self, name, url, introduced_at, options={}, location=None):
        self.name = name
        self.url = url
        self.introduced_at = introduced_at
        self.options = options
        self.view_fn = None
        self.docs = None
        self._request_schema = None
        self._request_schema_location = None
        self._response_schema = None
        self._response_schema_location = None
        self._changelog = OrderedDict()
        self._changelog_locations = OrderedDict()
        if location is None:
            self.location = get_callsite_location()
        else:
            self.location = location

    @property
    def methods(self):
        return self.options.get('methods', ['GET'])

    @property
    def request_schema(self):
        return self._request_schema

    @request_schema.setter
    def request_schema(self, schema):
        if schema is not None:
            _validation.validate_schema(schema)
        self._request_schema = schema
        # this location is the last item in the dict, sadly
        self._request_schema_location = get_callsite_location()

    @property
    def response_schema(self):
        return self._response_schema

    @response_schema.setter
    def response_schema(self, schema):
        if schema is not None:
            _validation.validate_schema(schema)
        self._response_schema = schema
        # this location is the last item in the dict, sadly
        self._response_schema_location = get_callsite_location()

    def changelog(self, api_version, doc):
        """Add a changelog entry for this api."""
        doc = textwrap.dedent(doc).strip()
        self._changelog[api_version] = doc
        self._changelog_locations[api_version] = get_callsite_location()

    def __call__(self, fn):
        wrapped = fn
        if self.response_schema:
            wrapped = _validation.wrap_response(wrapped, self.response_schema)
        if self.request_schema:
            wrapped = _validation.wrap_request(wrapped, self.request_schema)

        location = get_callsite_location()
        # this will be the lineno of the last decorator, so we want one
        # below it for the actual function
        location['lineno'] += 1
        self.register_view(wrapped, location)
        return wrapped

    def register_view(self, view_fn, location=None, introduced_at=None):
        if self.view_fn is not None:
            raise InvalidAPI('api already has view registered')
        self.view_fn = view_fn
        self.view_fn_location = location
        if self.introduced_at is None:
            self.introduced_at = introduced_at
        if self.docs is None and self.view_fn.__doc__ is not None:
            self.docs = self.view_fn.__doc__.strip()

    # legacy view decorator
    def view(self, introduced_at):

        def decorator(fn):
            location = get_callsite_location()
            # this will be the lineno of the last decorator, so we want one
            # below it for the actual function
            location['lineno'] += 1

            # convert older style version strings
            if introduced_at == '1.0':
                self.introduced_at = 1
            elif introduced_at is not None:
                self.introduced_at = int(introduced_at)

            self.register_view(fn, location, introduced_at)

            # support for legacy @validate_{body,output} decorators
            # we don't know the order of decorators, so allow for both.
            # Note that if these schemas come from the @validate decorators,
            # they are already validated, so we set directly.
            fn._acceptable_metadata = self
            if self._request_schema is None:
                self._request_schema = getattr(fn, '_request_schema', None)
                self._request_schema_location = getattr(
                    fn, '_request_schema_location', None)
            if self._response_schema is None:
                self._response_schema = getattr(fn, '_response_schema', None)
                self._response_schema_location = getattr(
                    fn, '_response_schema_location', None)

            return fn

        return decorator
