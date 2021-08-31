# Copyright 2019 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).
from collections import namedtuple
import copy
from json import dumps as json_dumps
from json import loads as json_loads
from urllib.parse import urljoin
import responses
from acceptable._validation import validate
import re
from requests.utils import CaseInsensitiveDict

from .responses import responses_manager


class Attrs(object):
    """A utility class allowing the creation of namespaces from a dict.
    Also provides an iterator over the items of the original dict.

    This is used by both Service and ServiceMock to create their
    endpoints attributes.

    e.g:
    a = Attrs(dict(b=1, c=2))
    assert a.b == 1
    assert a.c == 2
    assert dir(a) == ['b', 'c']
    """
    def __init__(self, attrs):
        # I think python name mangling is ok here to help avoid collisions
        # between instance attributes and names in attrs
        self.__attrs = dict(attrs)

    def __dir__(self):
        return list(self.__attrs)

    def __getattr__(self, name):
        try:
            return self.__attrs[name]
        except KeyError:
            raise AttributeError(name)

    def __iter__(self):
        return iter(self.__attrs.items())


Call = namedtuple("Call", "request response error".split())


class CallRecorder(object):
    def __init__(self):
        self._calls = []

    def record(self, mock, request, response, error):
        self._calls.append((mock, Call(request, response, error)))

    def get_calls(self):
        return [c for m, c in self._calls]

    def get_calls_for(self, mock):
        return [c for m, c in self._calls if m == mock]

    def get_calls_for_matching(self, mock, pattern):
        if not hasattr(pattern, "search"):
            pattern = re.compile(pattern)
        return [c for c in self.get_calls_for(mock) if pattern.search(c.request.url)]

    def get_calls_matching(self, pattern):
        if not hasattr(pattern, "search"):
            pattern = re.compile(pattern)
        return [c for m, c in self._calls if pattern.search(c.request.url)]


EndpointSpec = namedtuple(
    "EndpointSpec", ["name", "location", "methods", "request_schema", "response_schema"]
)


VALIDATION_ERROR_TEXT = """
{}:
{!r}

did not match schema:
{!r}

for service {!r} endpoint {!r} on url {!r} errors where:
{!r}
"""


class EndpointMock(object):
    """Provides methods to check calls made to this endpoint mock
    """
    def __init__(
        self,
        call_recorder,
        service_name,
        name,
        methods,
        url,
        request_schema,
        response_schema,
        response_callback,
    ):
        self._call_recorder = call_recorder
        self._service_name = service_name
        self._name = name
        self._methods = methods
        self._url = url
        self._request_schema = request_schema
        self._response_schema = response_schema
        self._response_callback = response_callback

    @property
    def service_name(self):
        return self._service_name

    @property
    def name(self):
        return self._name

    @property
    def url(self):
        return self._url

    @property
    def methods(self):
        return list(self._methods)

    @property
    def call_recorder(self):
        return self._call_recorder

    def _validate(self, data_source_name, body, schema):
        if schema is not None:
            if body is None:
                error_list = ["Missing body"]
            else:
                if isinstance(body, bytes):
                    body = body.decode("utf-8")
                try:
                    data = json_loads(body)
                except ValueError as e :
                    error_list = ['JSON decoding error: {}'.format(e)]
                else:
                    error_list = validate(data, schema)
            if error_list:
                raise AssertionError(
                    VALIDATION_ERROR_TEXT.format(
                        data_source_name,
                        body,
                        schema,
                        self._service_name,
                        self._name,
                        self._url,
                        error_list,
                    )
                )

    def _validate_request(self, request):
        self._validate("request data", request.body, self._request_schema)

    def _validate_response(self, response_body):
        self._validate("response data", response_body, self._response_schema)

    def _record_response(
        self, request, response_status, response_headers, response_body
    ):
        # Shenanigans to get a response object like responses would
        # record in calls list
        def tmp_callback(request):
            return response_status, response_headers, response_body

        callback_response = responses.CallbackResponse(
            request.method, self._url, tmp_callback
        )
        response = callback_response.get_response(request)
        self._call_recorder.record(self, request, response, None)

    def _callback(self, request):
        try:
            self._validate_request(request)
            response_status, response_headers, response_body = self._response_callback(
                request
            )
            self._validate_response(response_body)
        except Exception as exc:
            self._call_recorder.record(self, request, None, exc)
            raise exc
        else:
            self._record_response(
                request, response_status, response_headers, response_body
            )
            return response_status, response_headers, response_body

    def get_calls(self):
        return self._call_recorder.get_calls_for(self)

    def get_last_call(self):
        return self.get_calls()[-1]

    def get_calls_matching(self, pattern):
        return self._call_recorder.get_calls_for_matching(self, pattern)

    def get_call_count(self):
        return len(self.get_calls())

    def was_called(self):
        return self.get_call_count() > 0


class EndpointMockContextManager(object):
    def __init__(
        self,
        methods,
        call_recorder,
        service_name,
        name,
        url,
        request_schema,
        response_schema,
        response_callback,
    ):
        self._methods = methods
        self._mock = EndpointMock(
            call_recorder,
            service_name,
            name,
            methods,
            url,
            request_schema,
            response_schema,
            response_callback,
        )

    def _start(self):
        responses_manager.attach_callback(
            self._methods, self._mock._url, self._mock._callback
        )

    def _stop(self):
        responses_manager.detach_callback(
            self._methods, self._mock._url, self._mock._callback
        )

    def __enter__(self):
        self._start()
        return self._mock

    def __exit__(self, *args):
        self._stop()


def response_callback_factory(status=200, headers=None, body=None, json=None):
    if headers is None:
        headers = CaseInsensitiveDict()
    else:
        headers = CaseInsensitiveDict(headers)
    if json is not None:
        assert body is None
        body = json_dumps(json).encode('utf-8')
        if 'Content-Type' not in headers:
            headers['Content-Type'] = 'application/json'
    def response_callback(request):
        return status, headers, body
    return response_callback


ok_no_content_response_callback = response_callback_factory()


class Endpoint(object):
    """Configurable endpoint.

    Callable to create a context manager which activates and returns a mock
    for this endpoint.
    """
    def __init__(self, base_url, service_name, endpoint_spec, response_callback=None):
        self._url = urljoin(base_url, endpoint_spec.location)
        self._service_name = service_name
        self._name = endpoint_spec.name
        self._methods = list(endpoint_spec.methods)
        self._request_schema = endpoint_spec.request_schema
        self._response_schema = endpoint_spec.response_schema
        self._response_callback = response_callback

    @property
    def service_name(self):
        return self._service_name

    @property
    def name(self):
        return self._name

    @property
    def url(self):
        return self._url

    @property
    def methods(self):
        return list(self._methods)

    def disable_request_validation(self):
        self._request_schema = None

    def disable_response_validation(self):
        self._response_schema = None

    def disable_validation(self):
        self.disable_request_validation()
        self.disable_response_validation()

    def set_request_schema(self, schema):
        self._request_schema = schema

    def set_response_schema(self, schema):
        self._response_schema = schema

    def set_response_callback(self, callback):
        self._response_callback = callback

    def set_response(self, status=200, headers=None, body=None, json=None):
        self._response_callback = response_callback_factory(status, headers, body, json)

    def __call__(self, response_callback=None, call_recorder=None):
        if call_recorder is None:
            call_recorder = CallRecorder()
        if response_callback is None:
            response_callback = self._response_callback
            if response_callback is None:
                response_callback = ok_no_content_response_callback
        return EndpointMockContextManager(
            self._methods,
            call_recorder,
            self._service_name,
            self._name,
            self._url,
            self._request_schema,
            self._response_schema,
            response_callback,
        )


class ServiceMock(object):
    """Provides access to the endpoint mocks for this service and some functions
    to get calls made to the services endpoints.
     """
    def __init__(self, call_recorder, endpoints):
        self._call_recorder = call_recorder
        mocks = {}
        self._endpoint_context_managers = []
        for name, endpoint in endpoints.items():
            ecm = endpoint(call_recorder=call_recorder)
            mocks[name]= ecm._mock
            self._endpoint_context_managers.append(ecm)
        self.endpoints = Attrs(mocks)

    def get_calls(self):
        return self._call_recorder.get_calls()

    def get_calls_matching(self, pattern):
        return self._call_recorder.get_calls_matching(pattern)

    def get_call_count(self):
        return len(self.get_calls())

    def was_called(self):
        return self.get_call_count() > 0

    def _start(self):
        for ecm in self._endpoint_context_managers:
            ecm._start()

    def _stop(self):
        for ecm in self._endpoint_context_managers:
            ecm._stop()


class ServiceMockContextManager(object):
    def __init__(self, call_recorder, endpoints):
        self._mock = ServiceMock(call_recorder, endpoints)

    def __enter__(self):
        self._mock._start()
        return self._mock

    def __exit__(self, *args):
        self._mock._stop()


class Service(object):
    """Has configurable endpoints (.endpoints.*).

    Callable to create a context manager which will mock all the endpoints on
    the service.

    Endpoints can also be individually called to return a context manager
    which just mocks that endpoint.
    """
    def __init__(self, base_url, name, endpoint_specs):
        self._base_url = base_url
        self._name = name
        endpoints = {}
        for endpoint_spec in endpoint_specs:
            endpoints[endpoint_spec.name] = Endpoint(self._base_url, self._name, endpoint_spec)
        self.endpoints = Attrs(endpoints)

    @property
    def name(self):
        return self._name

    @property
    def base_url(self):
        return self._base_url

    def __call__(self, call_recorder=None):
        if call_recorder is None:
            call_recorder = CallRecorder()
        return ServiceMockContextManager(call_recorder, dict(self.endpoints))


class ServiceFactory(object):
    """Callable to create Service instances.

    You can create multiple instances of a Service and configure each
    independently.
    """
    def __init__(self, name, endpoint_specs):
        self._name = name
        self._endpoint_specs = endpoint_specs

    @property
    def name(self):
        return self._name

    def __call__(self, base_url):
        return Service(base_url, self.name, self._endpoint_specs)


__ALL__ = ['responses_mock_context', 'response_callback_factory', 'ServiceFactory', 'EndpointSpec', 'Endpoint']
