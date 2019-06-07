# Copyright 2019 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).

from future import standard_library

standard_library.install_aliases()

from acceptable.mocks import CallRecorder, Endpoint, EndpointMock, EndpointSpec, Service, ServiceFactory, responses_mock_context
import requests
import testtools
from testtools import ExpectedException
from testtools.matchers import Equals, HasLength
from testtools.assertions import assert_that


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
        assert_that(mock._callback(request), Equals(response_tuple))

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
        with ExpectedException(AssertionError):
            mock._callback(request)


class ServiceTests(testtools.TestCase):
    def make_test_service(self):
        endpoints = [
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
        ]
        service_factory = ServiceFactory(
            "test-service",
            endpoints,
        )
        service = service_factory("http://example.com")
        service.endpoints.test_endpoint.set_response(json=999)
        return service

    def test_simple_endpoint_cm(self):
        service = self.make_test_service()
        with service.endpoints.test_endpoint() as mock:
            requests.get("http://example.com/test-endpoint", json=888)
            assert_that(mock.get_calls(), HasLength(1))

    def test_service_cm(self):
        service = self.make_test_service()
        with service() as mock:
            requests.get("http://example.com/test-endpoint", json=888)
            assert_that(mock.endpoints.test_endpoint.get_calls(), HasLength(1))

    def test_validation_failure(self):
        service = self.make_test_service()
        with service() as mock:
            with ExpectedException(AssertionError):
                requests.get("http://example.com/test-endpoint", json="string")
        assert_that(mock.endpoints.test_endpoint.get_calls(), HasLength(1))

    def test_responses_manager_resets_responses_mock(self):
        service = self.make_test_service()
        with service() as service_mock:
            with responses_mock_context() as responses_mock:
                responses_mock.add('GET', 'http://exmaple.com/responses-test', b'test')
                requests.get("http://example.com/test-endpoint", json=888)
                requests.get("http://exmaple.com/responses-test")
                assert_that(responses_mock.calls, HasLength(2), 'RequestMock call count inside 2')
            assert_that(responses_mock.calls, HasLength(2), 'RequestMock call count inside 1')
        assert_that(responses_mock.calls, HasLength(0), 'RequestMock call count outside')

    def test_calls_matching(self):
        service = self.make_test_service()
        with service() as service_mock:
            requests.get("http://example.com/test-endpoint", json=888)
            requests.get("http://example.com/no-validation")
            assert_that(service_mock.get_calls_matching('no-validation$'), HasLength(1))

    def test_endpoint_missing_body(self):
        ep = Endpoint('http://example.com', 'test', EndpointSpec('endpoint', 'endpoint', ['GET'], True, None))
        with ep() as mock:
            with ExpectedException(AssertionError):
                requests.get("http://example.com/endpoint")

    def test_endpoint_empty_body_json_decoding_error(self):
        ep = Endpoint('http://example.com', 'test', EndpointSpec('endpoint', 'endpoint', ['GET'], True, None))
        with ep() as mock:
            with ExpectedException(AssertionError):
                requests.get("http://example.com/endpoint", data=b'')

