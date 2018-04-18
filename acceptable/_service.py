# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).

"""acceptable - Programatic API Metadata for Flask apps."""


class AcceptableService:
    """Main entry point for a service using acceptable to manage API versions.

    This class manages a set of API endpoints for a given service. An instance
    of this class is required to create an API endpoint.
    """
    NAME_ALREADY = 'API {} is already registered in service {}'
    URL_ALREADY = 'URL {} {} is already in service {}'

    def __init__(self, name):
        """Create an instance of AcceptableService.

        :param name: The service name.
        :raises TypeError: If the name string is something other than a
            string.
        """
        if not isinstance(name, str):
            raise TypeError(
                "name must be a string, not %s" % type(name).__name__)
        self.name = name
        self.apis = {}
        self.urls = set()

    def api(self, url, name, **options):
        """Add an API to the service.

        :param url: This is the url that the API should be registered at.
        :param name: This is the name of the api, and will be registered with
            flask apps under.

        Other keyword arguments may be used, and they will be passed to the
        flask application when initialised. Of particular interest is the
        'methods' keyword argument, which can be used to specify the HTTP
        method the URL will be added for.
        """
        assert name not in self.apis, self.NAME_ALREADY.format(name, self.name)
        methods = tuple(options.get('methods', ('GET',)))
        assert (url, methods) not in self.urls, self.URL_ALREADY.format(
            '|'.join(methods), url, self.name)

        api = AcceptableAPI(self, name, url, options)
        self.apis[name] = api
        self.urls.add((url, methods))
        return api

    def bind(self, flask_app):
        """Bind the service API urls to a flask app."""
        for name, api in self.apis.items():
            # only bind APIs that have views associated with them
            if api.view_fn is None:
                continue
            if name not in flask_app.view_functions:
                flask_app.add_url_rule(
                    api.url, name, view_func=api.view_fn, **api.options)

    # b/w compat
    initialise = bind


class AcceptableAPI:
    """Metadata abount an api endpoint."""

    def __init__(self, service, name, url, options):
        self.service = service
        self.name = name
        self.url = url
        self.options = options
        self.introduced_at = None
        self.view_fn = None

    def view(self, introduced_at):
        assert self.view_fn is None, 'api already has view registered'

        def wrapper(fn):
            self.register_view(introduced_at, fn)
            return fn
        return wrapper

    def register_view(self, introduced_at, view_fn):
        # legacy support
        if introduced_at == '1.0':
            self.introduced_at = 1
        else:
            self.introduced_at = int(introduced_at)
        self.view_fn = view_fn
