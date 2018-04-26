# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).

from fixtures import Fixture
from flask import Flask
from testtools import TestCase
from testtools.matchers import (
    Equals,
    Matcher,
)

from acceptable._service import (
    APIMetadata,
    AcceptableAPI,
    AcceptableService,
)
from acceptable._validation import (
    validate_body,
    validate_output,
)


class APIMetadataTestCase(TestCase):

    def test_register_api_duplicate_name(self):
        metadata = APIMetadata()
        api1 = AcceptableAPI('api', '/api1', 1)
        api2 = AcceptableAPI('api', '/api2', 1)
        metadata.register_service('test', None)
        metadata.register_api('test', None, api1)
        self.assertRaises(
            AssertionError,
            metadata.register_api,
            'other', None, api2,
        )

    def test_register_api_duplicate_url(self):
        metadata = APIMetadata()
        api1 = AcceptableAPI('api1', '/api', 1)
        api2 = AcceptableAPI('api2', '/api', 1)
        metadata.register_service('test', None)
        metadata.register_service('other', None)
        metadata.register_api('test', None, api1)
        self.assertRaises(
            AssertionError,
            metadata.register_api,
            'other', None, api2,
        )

    def test_register_api_allow_different_methods(self):
        metadata = APIMetadata()
        api1 = AcceptableAPI('api1', '/api', 1)
        api2 = AcceptableAPI('api2', '/api', 1, options={'methods': ['POST']})
        metadata.register_service('test', None)
        metadata.register_service('other', None)
        metadata.register_api('test', None, api1)
        metadata.register_api('other', None, api2)

    def test_register_service_handles_multiple(self):
        metadata = APIMetadata()
        api = AcceptableAPI('api', '/api', 1)

        metadata.register_service('test', None)
        self.assertEqual(
            metadata.services['test', None], {})

        metadata.register_api('test', None, api)
        self.assertEqual(
            metadata.services['test', None], {'api': api})

        # register service again, shouldn't remove any apis
        metadata.register_service('test', None)
        self.assertEqual(
            metadata.services['test', None], {'api': api})

    def test_bind_works(self):
        app = Flask(__name__)
        metadata = APIMetadata()
        metadata.register_service('test', None)
        api1 = AcceptableAPI('api1', '/api1', 1)
        api2 = AcceptableAPI('api2', '/api2', 1)
        metadata.register_api('test', None, api1)
        metadata.register_api('test', None, api2)

        @api1.view(introduced_at=1)
        def api1_impl():
            return 'api1'

        metadata.bind(app, 'test')

        self.assertEquals(api1_impl, app.view_functions['api1'])
        self.assertNotIn('api2', app.view_functions)

        resp = app.test_client().get('/api1')
        self.assertThat(resp, IsResponse('api1'))


class AcceptableServiceTestCase(TestCase):

    def test_raises_TypeError_on_construction(self):
        self.assertRaisesRegex(
            TypeError,
            "name must be a string, not object",
            AcceptableService,
            object(),
        )

    def test_can_register_url_route(self):
        def view():
            return "test view", 200

        service = AcceptableService('service', metadata=APIMetadata())
        api = service.api('/foo', 'foo_api')
        api.register_view(view, '1.0')

        app = Flask(__name__)
        service.bind(app)

        client = app.test_client()
        resp = client.get('/foo')

        self.assertThat(resp, IsResponse('test view'))


class ServiceFixture(Fixture):
    """A reusable fixture that sets up several API endpoints."""

    def _setUp(self):
        self.metadata = APIMetadata()
        self.service = AcceptableService('service', metadata=self.metadata)
        foo_api = self.service.api('/foo', 'foo_api', methods=['POST'])

        @foo_api.view(introduced_at='1.0')
        def foo():
            return "foo", 200

    def bind(self, app=None):
        if app is None:
            app = Flask(__name__)
        self.service.bind(app)
        return app


class AcceptableAPITestCase(TestCase):

    def test_acceptable_api_declaration_works(self):
        fixture = self.useFixture(ServiceFixture())
        api = fixture.service.api('/new', 'blah')

        self.assertEqual(api.url, '/new')
        self.assertEqual(api.options, {})
        self.assertEqual(api.name, 'blah')
        self.assertEqual(
            api, fixture.metadata.services['service', None]['blah'])

    def test_view_decorator_and_bind_works(self):
        fixture = self.useFixture(ServiceFixture())

        new_api = fixture.service.api('/new', 'blah')

        @new_api.view(introduced_at=1)
        def new_view():
            return "new view", 200

        app = fixture.bind()

        client = app.test_client()
        resp = client.get('/new')

        self.assertThat(resp, IsResponse("new view"))
        view = app.view_functions['blah']
        self.assertEqual(view.__name__, 'new_view')

    def test_view_introduced_at_string(self):
        fixture = self.useFixture(ServiceFixture())

        new_api = fixture.service.api('/new', 'blah')
        self.assertEqual(new_api.introduced_at, None)

        @new_api.view(introduced_at='1')
        def new_view():
            return "new view", 200

        self.assertEqual(new_api.introduced_at, 1)

    def test_view_introduced_at_1_0_string(self):
        fixture = self.useFixture(ServiceFixture())
        new_api = fixture.service.api('/new', 'blah')
        self.assertEqual(new_api.introduced_at, None)

        @new_api.view(introduced_at='1.0')
        def new_view():
            return "new view", 200

        self.assertEqual(new_api.introduced_at, 1)

    def test_can_still_call_view_directly(self):
        fixture = self.useFixture(ServiceFixture())

        new_api = fixture.service.api('/new', 'namegoeshere')

        @new_api.view(introduced_at=1)
        def new_view():
            return "new view", 200

        app = fixture.bind()
        with app.test_request_context('/new'):
            content, status = new_view()

        self.assertEqual(content, "new view")
        self.assertEqual(status, 200)

    def test_cannot_duplicate_name(self):
        fixture = self.useFixture(ServiceFixture())

        self.assertRaises(
            AssertionError,
            fixture.service.api,
            '/bar',
            'foo_api',
        )

    def test_cannot_duplicate_url_and_method(self):
        fixture = self.useFixture(ServiceFixture())
        self.assertRaises(
            AssertionError,
            fixture.service.api,
            '/foo',
            'bar',
            methods=['POST'],
        )

    def test_can_duplicate_url_different_method(self):
        fixture = self.useFixture(ServiceFixture())

        alt_api = fixture.service.api('/foo', 'foo_alt', methods=['GET'])

        @alt_api.view(introduced_at=1)
        def foo_alt():
            return "alt foo", 200

        app = fixture.bind()
        client = app.test_client()
        resp = client.get('/foo')

        self.assertThat(resp, IsResponse("alt foo"))


class LegacyAcceptableAPITestCase(TestCase):
    def test_validate_body_records_metadata(self):
        fixture = self.useFixture(ServiceFixture())
        new_api = fixture.service.api('/new', 'blah')
        schema = {'type': 'object'}

        @new_api.view(introduced_at=1)
        @validate_body(schema)
        def new_view():
            return "new view", 200

        self.assertEqual(
            schema,
            fixture.service.apis['blah'].request_schema,
        )

    def test_validate_body_records_metadata_reversed_order(self):
        fixture = self.useFixture(ServiceFixture())
        new_api = fixture.service.api('/new', 'blah')
        schema = {'type': 'object'}

        @validate_body(schema)
        @new_api.view(introduced_at=1)
        def new_view():
            return "new view", 200

        self.assertEqual(
            schema,
            fixture.service.apis['blah'].request_schema,
        )

    def test_validate_output_records_metadata(self):
        fixture = self.useFixture(ServiceFixture())
        new_api = fixture.service.api('/new', 'blah')
        schema = {'type': 'object'}

        @new_api.view(introduced_at=1)
        @validate_output(schema)
        def new_view():
            return "new view", 200

        self.assertEqual(
            schema,
            fixture.service.apis['blah'].response_schema,
        )

    def test_validate_output_records_metadata_reversed(self):
        fixture = self.useFixture(ServiceFixture())
        new_api = fixture.service.api('/new', 'blah')
        schema = {'type': 'object'}

        @validate_output(schema)
        @new_api.view(introduced_at=1)
        def new_view():
            return "new view", 200

        self.assertEqual(
            schema,
            fixture.service.apis['blah'].response_schema,
        )

    def test_validate_both_records_metadata(self):
        fixture = self.useFixture(ServiceFixture())
        new_api = fixture.service.api('/new', 'blah')
        schema1 = {'type': 'object'}
        schema2 = {'type': 'array'}

        @new_api.view(introduced_at=1)
        @validate_body(schema1)
        @validate_output(schema2)
        def new_view():
            return "new view", 200

        self.assertEqual(
            schema1,
            fixture.service.apis['blah'].request_schema,
        )
        self.assertEqual(
            schema2,
            fixture.service.apis['blah'].response_schema,
        )


class IsResponse(Matcher):

    def __init__(self, expected_content, expected_code=200, decode=None):
        """Construct a new IsResponse matcher.

        :param expected_content: The content you want to match against the
            response body. This can either be a matcher, a string, or a
            bytestring.

        :param expected_code: Tht HTTP status code you want to match against.

        :param decode: Whether to decode the response data according to the
            response charset. This can either be set implicitly or explicitly.
            If the 'expected_content' parameter is a string, this will
            implicitly be set to True. If 'expected_content' is a bytestring,
            this will be set to False. If 'expected_content' is a matcher,
            this will be set to True. Setting this parameter to a value
            explicitly disables this implicit behavior.
        """
        if isinstance(expected_content, str):
            self._decode = True
            expected_content = Equals(expected_content)
        elif isinstance(expected_content, bytes):
            self._decode = False
            expected_content = Equals(expected_content)
        else:
            self._decode = decode or True
        self.expected_content = expected_content
        self.expected_code = Equals(expected_code)

    def match(self, response):
        mismatch = self.expected_code.match(response.status_code)
        if mismatch:
            return mismatch
        data = response.data
        if self._decode:
            data = data.decode(response.charset)
        return self.expected_content.match(data)

    def __str__(self):
        return "IsResponse(%r, %r)" % (
            self.expected_content, self.expected_code)
