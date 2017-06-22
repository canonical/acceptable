# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).

"""Service Double implementation.

The ServiceMock class in this file is used at test-run-time to mock out a call
to a remote service API view.
"""
import functools
import urllib.parse
import json

from fixtures import Fixture
import responses


from acceptable._validation import validate


def service_mock(service, methods, url, input_schema, output_schema):
    return functools.partial(
        ServiceMock,
        service, methods, url, input_schema, output_schema)


SERVICE_LOCATIONS = {}


def set_service_locations(service_locations):
    global SERVICE_LOCATIONS
    SERVICE_LOCATIONS = service_locations


def get_service_locations():
    global SERVICE_LOCATIONS
    return SERVICE_LOCATIONS


class ServiceMock(Fixture):

    # Responses requires that only one instance of RequestsMock is active at
    # once. More accurately: each activation of a RequestsMock will overwrite
    # the previous one.
    # Since we want each ServiceMock instance to be activatable separately, we
    # have a single RequestsMock instance shared across all ServiceMock
    # instances. This may cause bugs or unexpected behavior since the lifetime
    # of the service mock will be extended to be the lifetime of the longest
    # service mock.
    _requests_mock = None

    def __init__(self, service, methods, url, input_schema, output_schema,
                 output, output_status=200):
        super().__init__()
        self._service = service
        self._methods = methods
        self._url = url
        self._input_schema = input_schema
        self._output_schema = output_schema
        self._output = output
        self._output_status = output_status

    def _setUp(self):
        if self._output_schema:
            error_list = validate(self._output, self._output_schema)
            if error_list:
                msg = (
                    "While setting up a service mock for the '{s._service}' "
                    "service's '{s._url}' endpoint, the specified output "
                    "does not match the service's endpoint output schema.\n\n"
                    "The errors are:\n{errors}\n\n"
                ).format(s=self, errors='\n'.join(error_list))
                raise AssertionError(msg)

        config = get_service_locations()
        service_location = config.get(self._service)
        if service_location is None:
            raise AssertionError(
                "A service mock for the '%s' service was requested, but the "
                "mock has not been configured with a location for that "
                "service. Ensure set_service_locations has been "
                "called before the mock is required, and that the locations "
                "dictionary contains a key for the '%s' service."
                % (self._service, self._service)
            )

        full_url = urllib.parse.urljoin(service_location, self._url)

        def _callback(request):
            if self._input_schema:
                payload = json.loads(request.body.decode())
                error_list = validate(payload, self._input_schema)
                if error_list:
                    # TODO: raise AssertionError here, since this is in a test?
                    return (
                        400,
                        {'Content-Type': 'application/json'},
                        json.dumps(error_list),
                    )
            # TODO: Do we need to support more than just json responses?
            return (
                self._output_status,
                {"Content-Type": "application/json"},
                json.dumps(self._output)
            )

        if ServiceMock._requests_mock is None:
            ServiceMock._requests_mock = responses.RequestsMock(
                assert_all_requests_are_fired=False
            )
            self.addCleanup(ServiceMock._clean_requests_mock)
            ServiceMock._requests_mock.start()
            self.addCleanup(ServiceMock._requests_mock.stop)

        for method in self._methods:
            self._requests_mock.add_callback(method, full_url, _callback)

    @property
    def calls(self):
        return self._requests_mock.calls

    @classmethod
    def _clean_requests_mock(cls):
        cls._requests_mock = None
