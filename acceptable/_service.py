# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).

"""acceptable - Programatic API Metadata for Flask apps."""
from acceptable import _validation


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

    def clear(self):
        self.services.clear()
        self.api_names.clear()
        self.urls.clear()


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
        self.request_schema = None
        self.response_schema = None
        self._docs = None
        self._changelog = []

    @property
    def methods(self):
        return self.options.get('methods', ['GET'])

    @property
    def docs(self):
        if self._docs is not None:
            return self._docs
        elif self.view_fn is not None:
            if self.view_fn.__doc__ is not None:
                return self.view_fn.__doc__.strip()

    @docs.setter
    def docs(self, value):
        self._docs = value

    def view(self, introduced_at):
        if self.view_fn is not None:
            raise InvalidAPI('api already has view registered')

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
        # we don't know the order of decorators, so allow for both.
        view_fn._acceptable_metadata = self
        self.request_schema = getattr(view_fn, '_request_schema', None)
        self.response_schema = getattr(view_fn, '_response_schema', None)
