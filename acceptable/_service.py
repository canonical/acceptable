# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).

"""acceptable - Programatic API Metadata for Flask apps."""
from collections import OrderedDict, defaultdict
import textwrap

from acceptable import _validation
from acceptable.util import (
    clean_docstring,
    get_callsite_location,
    sort_schema,
)


class InvalidAPI(Exception):
    pass


class APIMetadata():
    """Global datastructure for all services.

    Provides a single point to register apis against, so we can easily inspect
    and verify uniqueness.
    """

    def __init__(self):
        self.services = OrderedDict()
        self.api_names = set()
        self.urls = set()
        self._current_version = None

    def register_service(self, service, group, docs=None, title=None):
        if service not in self.services:
            self.services[service] = OrderedDict()

        if group not in self.services[service]:
            self.services[service][group] = APIGroup(group, docs, title)
        elif docs is not None:
            additional_docs = '\n' + clean_docstring(docs)
            self.services[service][group].docs += additional_docs

        return self.services[service][group]

    def register_api(self, service, group, api):
        # check for name/url clashes globally
        # FIXME: this should probably be per service?
        if api.name in self.api_names:
            raise InvalidAPI(
                'API {} is already registered in service {}'.format(
                    api.name, service)
            )
        self.api_names.add(api.name)

        if api.url is not None:
            url_key = (api.url, tuple(api.methods))
            if url_key in self.urls:
                raise InvalidAPI(
                    'URL {} {} is already in service {}'.format(
                        '|'.join(api.methods), api.url, service)
                )
            self.urls.add(url_key)

        self.services[service][group][api.name] = api

    @property
    def current_version(self):
        if self._current_version is None:
            versions = set()
            for service in self.services.values():
                for group in service.values():
                    for api in group.values():
                        versions.add(api.introduced_at)
                        if api._changelog:
                            versions.add(max(api._changelog))
            if versions:
                self._current_version = max(versions)
        return self._current_version

    def bind(self, flask_app, service, group=None):
        """Bind the service API urls to a flask app."""
        if group not in self.services[service]:
            raise RuntimeError(
                'API group {} does not exist in service {}'.format(
                    group, service)
            )
        for name, api in self.services[service][group].items():
            # only bind APIs that have views associated with them
            if api.view_fn is None:
                continue
            if name not in flask_app.view_functions:
                flask_app.add_url_rule(
                    api.url, name, view_func=api.view_fn, **api.options)

    def bind_all(self, flask_app):
        for service, groups in self.services.items():
            for group in groups:
                self.bind(flask_app, service, group)

    def clear(self):
        self.services.clear()
        self.api_names.clear()
        self.urls.clear()
        self._current_version = None

    def groups(self):
        for service, groups in self.services.items():
            for group in groups.values():
                yield service, group

    def serialize(self):
        """Serialize into JSONable dict, and associated locations data."""
        api_metadata = OrderedDict()
        # $ char makes this come first in sort ordering
        api_metadata['$version'] = self.current_version
        locations = {}

        for svc_name, group in self.groups():
            group_apis = OrderedDict()
            group_metadata = OrderedDict()
            group_metadata['apis'] = group_apis
            group_metadata['title'] = group.title
            api_metadata[group.name] = group_metadata

            if group.docs is not None:
                group_metadata['docs'] = group.docs

            for name, api in group.items():
                group_apis[name] = OrderedDict()
                group_apis[name]['service'] = svc_name
                group_apis[name]['api_group'] = group.name
                group_apis[name]['api_name'] = api.name
                group_apis[name]['introduced_at'] = api.introduced_at
                group_apis[name]['methods'] = api.methods
                group_apis[name]['request_schema'] = api.request_schema
                group_apis[name]['response_schema'] = api.response_schema
                group_apis[name]['params_schema'] = api.params_schema
                group_apis[name]['doc'] = api.docs
                group_apis[name]['changelog'] = api._changelog
                if api.title:
                    group_apis[name]['title'] = api.title
                else:
                    title = name.replace('-', ' ').replace('_', ' ').title()
                    group_apis[name]['title'] = title

                group_apis[name]['url'] = api.resolve_url()

                if api.undocumented:
                    group_apis[name]['undocumented'] = True
                if api.deprecated_at is not None:
                    group_apis[name]['deprecated_at'] = api.deprecated_at

                locations[name] = {
                    'api': api.location,
                    'request_schema': api._request_schema_location,
                    'response_schema': api._response_schema_location,
                    'params_schema': api._params_schema_location,
                    'changelog': api._changelog_locations,
                    'view': api.view_fn_location,
                }

        return api_metadata, locations


_metadata = None


def get_metadata():
    global _metadata
    if _metadata is None:
        _metadata = APIMetadata()
    return _metadata


def clear_metadata():
    global _metadata
    _metadata = None


class APIGroup(OrderedDict):
    """Wrapper for collection of APIs, with associated documentation."""
    def __init__(self, name=None, docs=None, title=None):
        self.name = name
        self.title = title
        if self.name is None:
            self.name = 'default'
            self.title = 'Default'
        elif title is None:
            self.title = name.replace('-', ' ').title()
        self.docs = docs
        super().__init__()


class AcceptableService():
    """User facing API for a service using acceptable to manage API versions.

    This provides a nicer interface to manage the global API metadata within
    a single file.

    It is just a factory and proxy to the global metadata state, it does not
    store any API state internally.
    """

    def __init__(self, name, group=None, title=None, metadata=None):
        """Create an instance of AcceptableService.

        :param name: The service name.
        :param group: An arbitrary API group within a service.
        """
        self.name = name
        self.group = group
        if metadata is None:
            self.metadata = get_metadata()
        else:
            self.metadata = metadata

        self.location = get_callsite_location()
        self.doc = None
        module = self.location['module']
        docs = None
        if module and module.__doc__:
            docs = clean_docstring(module.__doc__)
        self.metadata.register_service(name, group, docs, title)

    @property
    def apis(self):
        return self.metadata.services[self.name][self.group]

    def api(self,
            url,
            name,
            introduced_at=None,
            undocumented=False,
            deprecated_at=None,
            title=None,
            **options):
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
            self,
            name,
            url,
            introduced_at,
            options,
            undocumented=undocumented,
            deprecated_at=deprecated_at,
            title=title,
            location=location,
        )
        self.metadata.register_api(self.name, self.group, api)
        return api

    def django_api(
            self,
            name,
            introduced_at,
            undocumented=False,
            deprecated_at=None,
            title=None,
            **options):
        """Add a django API handler to the service.

        :param name: This is the name of the django url to use.

        The 'methods' paramater can be supplied as normal, you can also user
        the @api.handler decorator to link this API to its handler.

        """
        from acceptable.djangoutil import DjangoAPI
        location = get_callsite_location()
        api = DjangoAPI(
            self,
            name,
            introduced_at,
            options,
            location=location,
            undocumented=undocumented,
            deprecated_at=deprecated_at,
            title=title,
        )
        self.metadata.register_api(self.name, self.group, api)
        return api

    def bind(self, flask_app):
        """Bind the service API urls to a flask app."""
        self.metadata.bind(flask_app, self.name, self.group)

    # b/w compat
    initialise = bind


class AcceptableAPI():
    """Metadata about an api endpoint."""

    def __init__(
            self,
            service,
            name,
            url,
            introduced_at,
            options={},
            location=None,
            undocumented=False,
            deprecated_at=None,
            title=None):

        self.service = service
        self.name = name
        self.url = url
        self.introduced_at = introduced_at
        self.options = options
        self.view_fn = None
        self.view_fn_location = None
        self.docs = None
        self._request_schema = None
        self._request_schema_location = None
        self._response_schema = None
        self._response_schema_location = None
        self._params_schema = None
        self._params_schema_location = None
        self._changelog = OrderedDict()
        self._changelog_locations = OrderedDict()
        if location is None:
            self.location = get_callsite_location()
        else:
            self.location = location
        self.undocumented = undocumented
        self.deprecated_at = deprecated_at
        self.title = title

    @property
    def methods(self):
        return list(self.options.get('methods', ['GET']))

    def resolve_url(self):
        return self.url

    @property
    def request_schema(self):
        return self._request_schema

    @request_schema.setter
    def request_schema(self, schema):
        if schema is not None:
            _validation.validate_schema(schema)
        self._request_schema = sort_schema(schema)
        # this location is the last item in the dict, sadly
        self._request_schema_location = get_callsite_location()

    @property
    def response_schema(self):
        return self._response_schema

    @response_schema.setter
    def response_schema(self, schema):
        if schema is not None:
            _validation.validate_schema(schema)
        self._response_schema = sort_schema(schema)
        # this location is the last item in the dict, sadly
        self._response_schema_location = get_callsite_location()

    @property
    def params_schema(self):
        return self._params_schema

    @params_schema.setter
    def params_schema(self, schema):
        if schema is not None:
            _validation.validate_schema(schema)
        self._params_schema = sort_schema(schema)
        self._params_schema_location = get_callsite_location()

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
            self.docs = clean_docstring(self.view_fn.__doc__)

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
            if self._params_schema is None:
                self._params_schema = getattr(fn, '_params_schema', None)
                self._params_schema_location = getattr(
                    fn, '_params_schema_location', None)
            return fn

        return decorator
