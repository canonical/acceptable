# Copyright 2019 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).

from future import standard_library

standard_library.install_aliases()

from acceptable.mocks import EndpointMock, ServiceFactory, EndpointSpec, CallRecorder, responses_mock_context
import requests
import testtools


class EventMockTests(testtools.TestCase):
    def test_successful_event_mock(self):
        call_recorder = CallRecorder()
        response_tuple = (200, {}, b"999\n")
        mock = EndpointMock(
            call_recorder,
            "service",
            "api",
            "http://example.com",
            request_schema={"type": "string"},
            response_schema={"type": "number"},
            response_callback=lambda req: response_tuple,
        )
        request = requests.Request("GET", "http://example.com", json="hello").prepare()
        self.assertEquals(response_tuple, mock._callback(request))

    def test_validation_failure_event_mock(self):
        call_recorder = CallRecorder()
        mock = EndpointMock(
            call_recorder,
            "service",
            "api",
            "http://example.com",
            request_schema={"type": "number"},
            response_schema=None,
            response_callback=lambda req: (200, {}, b""),
        )
        request = requests.Request("GET", "http://example.com", json="hello").prepare()
        try:
            mock._callback(request)
        except AssertionError:
            pass
        else:
            raise AssertionError("Call should raise AssertionError")


class ServiceTests(testtools.TestCase):
    def make_test_service(self):
        service_factory = ServiceFactory(
            "test-service",
            [
                EndpointSpec(
                    "test_endpoint",
                    "test-endpoint",
                    ["GET", "POST"],
                    {"type": "number"},
                    {"type": "number"},
                ),
                EndpointSpec(
                    "no_validation",
                    "no-validation",
                    ["GET"],
                    None,
                    None,
                )
            ],
        )
        service = service_factory("http://example.com")
        service.test_endpoint.set_json_response(200, {}, 999)
        return service

    def test_simple_endpoint_cm(self):
        service = self.make_test_service()
        with service.test_endpoint() as mock:
            requests.get("http://example.com/test-endpoint", json=888)
            self.assertEqual(1, len(mock.calls))

    def test_service_cm(self):
        service = self.make_test_service()
        with service() as mock:
            requests.get("http://example.com/test-endpoint", json=888)
            self.assertEqual(1, len(mock.test_endpoint.calls))

    def test_validation_failure(self):
        service = self.make_test_service()
        with service() as mock:
            try:
                requests.get("http://example.com/test-endpoint", json="string")
            except AssertionError:
                pass
            else:
                raise AssertionError("Validation did not fail")
        self.assertEqual(1, len(mock.test_endpoint.calls))

    def test_responses_manager(self):
        service = self.make_test_service()
        with service() as service_mock:
            with responses_mock_context() as responses_mock:
                responses_mock.add('GET', 'http://exmaple.com/responses-test', b'test')
                requests.get("http://example.com/test-endpoint", json=888)
                requests.get("http://exmaple.com/responses-test")
                self.assertEqual(1, len(service_mock.test_endpoint.calls), 'test_endpoint call count')
                self.assertEqual(2, len(responses_mock.calls), 'RequestMock call count inside 2')
            self.assertEqual(2, len(responses_mock.calls), 'RequestMock call count inside 1r')
        self.assertEqual(0, len(responses_mock.calls), 'RequestMock call count outside')

    def test_calls_matching(self):
        service = self.make_test_service()
        with service() as service_mock:
            requests.get("http://example.com/test-endpoint", json=888)
            requests.get("http://example.com/no-validation")
            self.assertEqual(1, len(service_mock.calls_matching('no-validation$')))