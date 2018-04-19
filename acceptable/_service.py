# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).

"""acceptable - Programatic API Metadata for Flask apps."""
from acceptable import _validation


class APIMetadata:
    """Global datastructure for all services.

    Provides a single point to register apis against, so we can easily inspect
    and verify uniqueness.
    """

    NAME_ALREADY = 'API {} is already registered in service {}'
    URL_ALREADY = 'URL {} {} is already in service {}'

    def __init__(self):
        self.services = {}
        self.api_names = set()
        self.urls = set()

    def register_service(self, name, group):
        if (name, group) not in self.services:
            self.services[name, group] = {}

    def register_api(self, name, group, api):
        assert api.name not in self.api_names, self.NAME_ALREADY.format(
            api.name, name)
        url_key = (api.url, api.methods)
        assert url_key not in self.urls, self.URL_ALREADY.format(
            '|'.join(api.methods), api.url, name)
        self.api_names.add(api.name)
        self.urls.add((api.url, api.methods))
        self.services[name, group][api.name] = api

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
        for name, group in self.services.items():
            self.bind(flask_app, name, group)


METADATA = APIMetadata()


class AcceptableService:
    """User facing API for a service using acceptable to manage API versions.

    This provides a nicer interface to manage the global API metadata within
    a single file.

    It is just a proxy to the global metadata state, it does not store any
    API state internally.
    """

    def __init__(self, name, group=None, metadata=METADATA):
        """Create an instance of AcceptableService.

        :param name: The service name.
        :param name: An arbitrary API group within a service.
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
        assert name not in self.apis, (
            'API {} is already registered in service {}'.format(
                name, self.name)
        )
        methods = tuple(options.get('methods', ('GET',)))
        assert (url, methods) not in self.urls, (
            'URL {} {} is already in service {}'.format(
                '|'.join(methods), url, self.name)
        )

        api = AcceptableAPI(name, url, introduced_at, options)
        self.metadata.register_api(self.name, self.group, api)
        return api

    def bind(self, flask_app):
        """Bind the service API urls to a flask app."""
        self.metadata.bind(flask_app, self.name, self.group)

    # b/w compat
    initialise = bind


class AcceptableAPI:
    """Metadata abount an api endpoint."""

    def __init__(self, name, url, introduced_at, options={}):
        self.name = name
        self.url = url
        self.introduced_at = introduced_at
        self.options = options
        self.view_fn = None

    @property
    def request_schema(self):
        return self._request_schema

    @request_schema.setter
    def request_schema(self, schema):
        if schema is not None:
            _validation.validate_schema(schema)
        self._request_schema = schema

    @property
    def response_schema(self):
        return self._response_schema

    @response_schema.setter
    def response_schema(self, schema):
        if schema is not None:
            _validation.validate_schema(schema)
        self._response_schema = schema

    @property
    def methods(self):
        return tuple(self.options.get('methods', ('GET',)))

    def view(self, introduced_at):
        assert self.view_fn is None, 'api already has view registered'

        def decorator(fn):
            self.register_view(fn, introduced_at)
            return fn
        return decorator

    def register_view(self, view_fn, introduced_at):
        # legacy support
        if introduced_at == '1.0':
            self.introduced_at = 1
        elif introduced_at is not None:
            self.introduced_at = int(introduced_at)
        self.view_fn = view_fn

        # support for legacy @validate_{body,output} decorators
        view_fn._acceptable_metadata = self
        # schema on the function have already been validated, so bypass the
        # validation here
        self._request_schema = getattr(view_fn, '_request_schema', None)
        self._response_schema = getattr(view_fn, '_response_schema', None)
