# Copyright 2019 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).
from future import standard_library

standard_library.install_aliases()

from collections import namedtuple
import copy
import json
from urllib.parse import urljoin
import responses
from acceptable._validation import validate
import re


class ResponsesManager(object):
    def __init__(self):
        self._attached = 0

    def _attach(self):
        if self._attached == 0:
            responses.mock.start()
        self._attached += 1

    def _detach(self):
        self._attached -= 1
        assert self._attached >= 0
        if self._attached == 0:
            responses.mock.stop()
            responses.mock.reset()

    def attach_callback(self, methods, url, callback):
        for method in methods:
            responses.mock.add_callback(method, url, callback)
        self._attach()

    def detach_callback(self, methods, url, callback):
        for method in methods:
            responses.mock.remove(method, url)
        self._detach()


_responses_manager = ResponsesManager()


class responses_mock_context(object):
    """A context manager to allow the safe (single threaded) use of the global
     responses mock.

     The object returned by this context manager is the responses.mock 
     RequestsMock object.

     You should us this context manager rather than any other instance of
     RequestsMock.
    """

    def __enter__(self):
        _responses_manager._attach()
        return responses.mock

    def __exit__(self, *args):
        _responses_manager._detach()


Call = namedtuple("Call", "request response error".split())


class CallRecorder(object):
    def __init__(self):
        self._calls = []

    def record(self, mock, request, response, error):
        self._calls.append((mock, Call(request, response, error)))

    @property
    def calls(self):
        return [c for m, c in self._calls]

    def calls_for(self, mock):
        return [c for m, c in self._calls if m == mock]

    def calls_for_matching(self, mock, pattern):
        if not hasattr(pattern, "search"):
            pattern = re.compile(pattern)
        return [c for c in self.calls_for(mock) if pattern.search(c.request.url)]

    def calls_matching(self, pattern):
        if not hasattr(pattern, "search"):
            pattern = re.compile(pattern)
        return [c for m, c in self._calls if pattern.search(c.request.url)]
        


EndpointSpec = namedtuple(
    "EndpointSpec", "name location methods request_schema response_schema".split()
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
    def __init__(
        self,
        call_recorder,
        service_name,
        name,
        url,
        request_schema,
        response_schema,
        response_callback,
    ):
        self._call_recorder = call_recorder
        self._service_name = service_name
        self._name = name
        self._url = url
        self._request_schema = request_schema
        self._response_schema = response_schema
        self._response_callback = response_callback

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
                data = json.loads(body)
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

    @property
    def calls(self):
        return self._call_recorder.calls_for(self)

    @property
    def last_call(self):
        return self.calls[-1]

    def calls_matching(self, pattern):
        return self._call_recorder.calls_for_matching(self, pattern)


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
            url,
            request_schema,
            response_schema,
            response_callback,
        )

    def _start(self):
        _responses_manager.attach_callback(
            self._methods, self._mock._url, self._mock._callback
        )

    def _stop(self):
        _responses_manager.detach_callback(
            self._methods, self._mock._url, self._mock._callback
        )

    def __enter__(self):
        self._start()
        return self._mock

    def __exit__(self, *args):
        self._stop()


def ok_no_content_response_callback(request):
    return 200, {}, None


class EndPoint(object):
    def __init__(self, service, endpoint_spec):
        self._service = service
        self._name = endpoint_spec.name
        self._url = None
        self._location = endpoint_spec.location
        self._methods = list(endpoint_spec.methods)
        self.request_schema = copy.deepcopy(endpoint_spec.request_schema)
        self.response_schema = copy.deepcopy(endpoint_spec.response_schema)
        self.response_callback = None

    @property
    def url(self):
        if self._url is None:
            return urljoin(self._service._base_url, self._location)
        return self._url

    @url.setter
    def url(self, value):
        self._url = value

    def set_response(self, response_status, response_headers, response_body):
        def response_callback(request):
            return response_status, response_headers, response_body

        self.response_callback = response_callback

    def set_json_response(self, response_status, response_headers, response_data):
        self.set_response(response_status, response_headers, json.dumps(response_data))

    def __call__(self, call_recorder=None):
        if call_recorder is None:
            call_recorder = CallRecorder()
        response_callback = self.response_callback
        if response_callback is None:
            response_callback = ok_no_content_response_callback
        return EndpointMockContextManager(
            self._methods,
            call_recorder,
            self._service._name,
            self._name,
            self.url,
            self.request_schema,
            self.response_schema,
            response_callback,
        )


class ServiceMock(object):
    def __init__(self, call_recorder, endpoints):
        self._call_recorder = call_recorder
        self._endpoint_cms = {
            name: endpoint(call_recorder=call_recorder)
            for name, endpoint in endpoints.items()
        }

    def calls_matching(self, pattern):
        return self._call_recorder.calls_matching(pattern)

    def _start(self):
        for endpoint_cm in self._endpoint_cms.values():
            endpoint_cm._start()

    def _stop(self):
        for endpoint_cm in self._endpoint_cms.values():
            endpoint_cm._stop()



    def __getattr__(self, name):
        try:
            return self._endpoint_cms[name]._mock
        except KeyError:
            return NameError(name)


class ServiceMockContextManager(object):
    def __init__(self, call_recorder, endpoints):
        self._mock = ServiceMock(call_recorder, endpoints)

    def __enter__(self):
        self._mock._start()
        return self._mock

    def __exit__(self, *args):
        self._mock._stop()


class Service(object):
    def __init__(self, _name, endpoint_specs, base_url):
        self._name = _name
        self._base_url = base_url
        self._endpoints = {}
        for endpoint_spec in endpoint_specs:
            self._endpoints[endpoint_spec.name] = EndPoint(self, endpoint_spec)

    def __getattr__(self, attr):
        try:
            return self._endpoints[attr]
        except KeyError:
            raise NameError(attr)

    def __call__(self, call_recorder=None):
        if call_recorder is None:
            call_recorder = CallRecorder()
        return ServiceMockContextManager(call_recorder, self._endpoints)


class ServiceFactory(object):
    def __init__(self, service_name, endpoint_specs):
        self._service_name = service_name
        self._endpoint_specs = endpoint_specs

    @property
    def name(self):
        return self._service_name

    def __call__(self, base_url):
        return Service(self.name, self._endpoint_specs, base_url)
