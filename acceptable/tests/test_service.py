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
    AcceptableService,
)


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

        service = AcceptableService('service')
        api = service.api('/foo', 'foo_api')
        api.register_view('1.0', view)

        app = Flask(__name__)
        service.bind(app)

        client = app.test_client()
        resp = client.get('/foo')

        self.assertThat(resp, IsResponse('test view'))


class ServiceFixture(Fixture):
    """A reusable fixture that sets up several API endpoints.

    This fixture creates a simple set of API endpoints with a mix of different
    version and API flag requirements. Tests can use this fixture instead of
    having to do all this setup in every test.
    """

    def _setUp(self):
        self.service = AcceptableService('service')
        foo_api = self.service.api('/foo', 'foo_api', methods=['POST'])
        foo_api.register_view('1.0', self.foo)

    def bind(self, app=None):
        if app is None:
            app = Flask(__name__)
        self.service.bind(app)
        return app

    def foo(self):
        return "foo", 200


class AcceptableAPITestCase(TestCase):

    def test_view_decorator_works(self):
        fixture = self.useFixture(ServiceFixture())

        new_api = fixture.service.api('/new', 'blah')

        @new_api.view(introduced_at='1.0')
        def new_view():
            return "new view", 200

        app = fixture.bind()

        client = app.test_client()
        resp = client.get('/new')

        self.assertThat(resp, IsResponse("new view"))
        view = app.view_functions['blah']
        self.assertEqual(view.__name__, 'new_view')

    def test_can_still_call_view_directly(self):
        fixture = self.useFixture(ServiceFixture())

        new_api = fixture.service.api('/new', 'namegoeshere')

        @new_api.view(introduced_at='1.0')
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

        @alt_api.view(introduced_at='1.0')
        def foo_alt():
            return "alt foo", 200

        app = fixture.bind()
        client = app.test_client()
        resp = client.get('/foo')

        self.assertThat(resp, IsResponse("alt foo"))


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
