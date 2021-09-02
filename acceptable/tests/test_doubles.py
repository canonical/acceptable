# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).
import json

import requests
from testtools import TestCase
from testtools.matchers import Contains


from acceptable._doubles import (
    ServiceMock,
    service_mock,
    set_service_locations,
)


class ServiceMockTests(TestCase):

    def setUp(self):
        super().setUp()
        # service locations are cached between tests. This should eventually
        # be fixed, but until then it's easier to set them to an empty dict at
        # the start of every test:
        set_service_locations({})

    def test_raises_on_incompatible_output_value(self):
        double = ServiceMock(
            service='foo',
            methods=['POST'],
            url='/',
            input_schema=None,
            output_schema={'type': 'object'},
            output=[]
        )
        # Note that we can't use 'double.setUp' as the method here, since the
        # fixture catches any exceptions raised by _setUp and re-raises a
        # different exception instance.
        e = self.assertRaises(AssertionError, double._setUp)
        self.assertThat(
            str(e),
            Contains(
                "While setting up a service mock for the 'foo' service's '/' "
                "endpoint, the specified output does not match the service's "
                "endpoint output schema."
            ))

    def test_raises_when_service_location_has_not_been_set(self):
        double = ServiceMock(
            service='foo',
            methods=['POST'],
            url='/',
            input_schema=None,
            output_schema={'type': 'array'},
            output=[]
        )
        e = self.assertRaises(AssertionError, double._setUp)
        self.assertEqual(
            "A service mock for the 'foo' service was requested, but the mock "
            "has not been configured with a location for that service. "
            "Ensure set_service_locations has been called before the mock is "
            "required, and that the locations dictionary contains a key for "
            "the 'foo' service.",
            str(e))

    def test_can_construct_double_with_output_schema(self):
        double = ServiceMock(
            service='foo',
            methods=['POST'],
            url='/',
            input_schema=None,
            output_schema={'type': 'array'},
            output=[]
        )
        set_service_locations(dict(foo="http://localhost:1234/"))

        self.useFixture(double)

        resp = requests.post("http://localhost:1234/")

        self.assertEqual(200, resp.status_code)
        self.assertEqual([], resp.json())

    def test_can_construct_double_with_input_schema_and_invalid_payload(self):
        double = ServiceMock(
            service='foo',
            methods=['POST'],
            url='/',
            input_schema={'type': 'object'},
            output_schema={'type': 'array'},
            output=[]
        )
        set_service_locations(dict(foo="http://localhost:1234/"))

        self.useFixture(double)

        resp = requests.post("http://localhost:1234/", json=[])

        self.assertEqual(400, resp.status_code)
        self.assertEqual(
            ["[] is not of type 'object' at /"],
            resp.json())

    def test_can_construct_double_with_input_schema_and_valid_payload(self):
        double = ServiceMock(
            service='foo',
            methods=['POST'],
            url='/',
            input_schema={'type': 'object'},
            output_schema={'type': 'array'},
            output=[]
        )
        set_service_locations(dict(foo="http://localhost:1234/"))

        self.useFixture(double)

        resp = requests.post("http://localhost:1234/", json={})

        self.assertEqual(200, resp.status_code)
        self.assertEqual([], resp.json())

    def test_can_construct_double_with_error_and_different_output_schema(self):
        error = {'error_list': {'code': 'test'}}
        double = ServiceMock(
            service='foo',
            methods=['POST'],
            url='/',
            input_schema=None,
            output_schema={'type': 'object'},
            output_status=400,
            output=error
        )
        set_service_locations(dict(foo="http://localhost:1234/"))

        self.useFixture(double)

        resp = requests.post("http://localhost:1234/")

        self.assertEqual(400, resp.status_code)
        self.assertEqual(error, resp.json())

    def test_can_construct_double_with_custom_headers(self):
        custom = {'Cool-Header': 'What a wonderful life'}
        double = ServiceMock(
            service='foo',
            methods=['POST'],
            url='/',
            input_schema=None,
            output_schema={'type': 'object'},
            output_headers=custom,
            output={'ok': True}
        )
        set_service_locations(dict(foo="http://localhost:1234/"))

        self.useFixture(double)

        resp = requests.post("http://localhost:1234/")

        self.assertEqual(200, resp.status_code)
        self.assertEqual({'ok': True}, resp.json())
        custom['Content-Type'] = 'application/json'
        self.assertEqual(custom, resp.headers)

    def test_can_construct_double_given_content_type_respected(self):
        custom = {'Content-Type': 'not-json'}
        double = ServiceMock(
            service='foo',
            methods=['POST'],
            url='/',
            input_schema=None,
            output_schema={'type': 'object'},
            output_headers=custom,
            output={'ok': True}
        )
        set_service_locations(dict(foo="http://localhost:1234/"))

        self.useFixture(double)

        resp = requests.post("http://localhost:1234/")

        self.assertEqual(200, resp.status_code)
        self.assertEqual({'ok': True}, resp.json())
        self.assertEqual(custom, resp.headers)

    def test_mock_records_calls(self):
        double = ServiceMock(
            service='foo',
            methods=['POST'],
            url='/',
            input_schema={'type': 'object'},
            output_schema={'type': 'array'},
            output=[]
        )
        set_service_locations(dict(foo="http://localhost:1234/"))

        self.useFixture(double)

        requests.post("http://localhost:1234/", json={'call': 1})
        requests.post("http://localhost:1234/", json={'call': 2})

        call1, call2 = double.calls
        self.assertEqual(
            json.loads(call1.request.body.decode()),
            {'call': 1}
        )
        self.assertEqual(
            json.loads(call2.request.body.decode()),
            {'call': 2}
        )

    def test_mock_regards_url(self):
        double = ServiceMock(
            service='foo',
            methods=['POST'],
            url='/foo',
            input_schema={'type': 'object'},
            output_schema={'type': 'array'},
            output=[]
        )
        set_service_locations(dict(foo="http://localhost:1234/"))

        self.useFixture(double)

        self.assertRaises(
            requests.exceptions.ConnectionError,
            requests.post,
            "http://localhost:1234/bar",
            json={}
        )

    def test_mock_regards_method(self):
        double = ServiceMock(
            service='foo',
            methods=['GET'],
            url='/foo',
            input_schema={'type': 'object'},
            output_schema={'type': 'array'},
            output=[]
        )
        set_service_locations(dict(foo="http://localhost:1234/"))

        self.useFixture(double)

        self.assertRaises(
            requests.exceptions.ConnectionError,
            requests.post,
            "http://localhost:1234/bar",
            json={}
        )

    def test_mock_works_with_multiple_methods(self):
        double = ServiceMock(
            service='foo',
            methods=['GET', 'POST', 'PATCH'],
            url='/foo',
            input_schema={'type': 'object'},
            output_schema={'type': 'array'},
            output=[]
        )
        set_service_locations(dict(foo="http://localhost:1234/"))

        self.useFixture(double)

        self.assertEqual(
            200,
            requests.post("http://localhost:1234/foo", json={}).status_code
        )
        self.assertEqual(
            200,
            requests.get("http://localhost:1234/foo", json={}).status_code
        )
        self.assertEqual(
            200,
            requests.patch("http://localhost:1234/foo", json={}).status_code
        )

    def test_mock_output_status(self):
        double = ServiceMock(
            service='foo',
            methods=['POST'],
            url='/foo',
            input_schema={'type': 'object'},
            output_schema={'type': 'array'},
            output=[],
            output_status=201
        )
        set_service_locations(dict(foo="http://localhost:1234/"))

        self.useFixture(double)

        self.assertEqual(
            201,
            requests.post("http://localhost:1234/foo", json={}).status_code
        )

    def test_service_mock(self):
        double_factory = service_mock(
            service='foo',
            methods=['GET'],
            url='/foo',
            input_schema={'type': 'object'},
            output_schema={'type': 'array'},
        )
        double = double_factory([])

        self.assertEqual('foo', double._service)
        self.assertEqual(['GET'], double._methods)
        self.assertEqual('/foo', double._url)
        self.assertEqual({'type': 'object'}, double._input_schema)
        self.assertEqual({'type': 'array'}, double._output_schema)
        self.assertEqual([], double._output)
