# -*- coding: utf-8 -*-
# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).

from operator import methodcaller

from fixtures import Fixture
from flask import Flask
from testscenarios import TestWithScenarios
from testtools import TestCase
from testtools.matchers import (
    Contains,
    Equals,
    Matcher,
)

from acceptable import (
    AcceptableService,
    EndpointMap,
    parse_accept_headers,
)


class AcceptableServiceTestCase(TestCase):

    def test_raises_TypeError_on_construction(self):
        self.assertRaisesRegex(
            TypeError,
            "vendor must be a string, not object",
            AcceptableService,
            object(), object()
        )

    def test_raises_ValueError_on_construction(self):
        self.assertRaisesRegex(
            ValueError,
            "vendor identifier must consist of alphanumeric "
            "characters only.",
            AcceptableService,
            "vendor.foo", object()
        )

    def test_can_register_url_route(self):
        def view():
            return "test view", 200

        app = Flask(__name__)
        service = AcceptableService('vendor', app)
        api = service.api('/foo')
        api.register_view('1.0', None, view)

        client = app.test_client()
        resp = client.get('/foo')

        self.assertThat(resp, IsResponse('test view'))

    def test_can_register_url_route_with_two_phase_registration(self):
        def view():
            return "test view", 200

        service = AcceptableService('vendor')
        api = service.api('/foo')
        api.register_view('1.0', None, view)

        app = Flask(__name__)
        service.initialise(app)

        client = app.test_client()
        resp = client.get('/foo')

        self.assertThat(resp, IsResponse('test view'))

    def test_can_rebind_api_to_second_flask_application(self):
        def view():
            return "test view", 200

        service = AcceptableService('vendor')
        api = service.api('/foo')
        api.register_view('1.0', None, view)

        app1 = Flask(__name__)
        app2 = Flask(__name__)
        service.initialise(app1)

        client = app1.test_client()
        resp = client.get('/foo')

        self.assertThat(resp, IsResponse('test view'))

        service.initialise(app2)
        client = app2.test_client()
        resp = client.get('/foo')

        self.assertThat(resp, IsResponse('test view'))

    def test_rebinding_to_existing_application_is_a_noop(self):
        def view():
            return "test view", 200

        service = AcceptableService('vendor')
        api = service.api('/foo')
        api.register_view('1.0', None, view)

        app1 = Flask(__name__)
        service.initialise(app1)
        service.initialise(app1)

        client = app1.test_client()
        resp = client.get('/foo')

        self.assertThat(resp, IsResponse('test view'))


class SimpleAPIServiceFixture(Fixture):
    """A reusable fixture that sets up several API endpoints.

    This fixture creates a simple set of API endpoints with a mix of different
    version and API flag requirements. Tests can use this fixture instead of
    having to do all this setup in every test.
    """

    def _setUp(self):
        self.flask_app = Flask(__name__)
        self.service = AcceptableService('vendor', self.flask_app)

        # The /foo API is POST only, and contains three different versioned
        # endpoints:
        foo_api = self.service.api('/foo', methods=['POST'])
        foo_api.register_view('1.0', None, self.foo_v10)
        foo_api.register_view('1.1', None, self.foo_v11)
        foo_api.register_view('1.3', None, self.foo_v13)
        foo_api.register_view('1.5', None, self.foo_v15)

        # The /flagged API is GET only, and has some API flags set:
        flagged_api = self.service.api('/flagged', methods=['GET'])
        flagged_api.register_view('1.3', None, self.flagged_v13)
        flagged_api.register_view('1.4', 'feature1', self.flagged_v14_feature1)
        flagged_api.register_view('1.4', 'feature2', self.flagged_v14_feature2)

    def foo_v10(self):
        return "Foo version 1.0", 200

    def foo_v11(self):
        return "Foo version 1.1", 200

    def foo_v13(self):
        return "Foo version 1.3", 200

    def foo_v15(self):
        return "Foo version 1.5", 200

    def flagged_v13(self):
        return "Flagged version 1.3", 200

    def flagged_v14_feature1(self):
        return "Flagged version 1.4 with feature1", 200

    def flagged_v14_feature2(self):
        return "Flagged version 1.4 with feature2", 200


class AcceptableAPITestCase(TestCase):

    def test_default_view_is_latest_version(self):
        fixture = self.useFixture(SimpleAPIServiceFixture())
        client = fixture.flask_app.test_client()
        resp = client.post('/foo')

        self.assertThat(resp, IsResponse("Foo version 1.5"))

    def test_can_select_specific_version(self):
        fixture = self.useFixture(SimpleAPIServiceFixture())
        client = fixture.flask_app.test_client()
        resp = client.post(
            '/foo',
            headers={'Accept': 'application/vnd.vendor.1.1'})

        self.assertThat(resp, IsResponse("Foo version 1.1"))

    def test_versions_are_downgraded(self):
        # Ask for version 1.2, but since it doesn't exist we'll
        # get the next oldest version instead.
        fixture = self.useFixture(SimpleAPIServiceFixture())
        client = fixture.flask_app.test_client()
        resp = client.post(
            '/foo',
            headers={'Accept': 'application/vnd.vendor.1.2'})

        self.assertThat(resp, IsResponse("Foo version 1.1"))

    def test_get_unflagged_view_by_default(self):
        fixture = self.useFixture(SimpleAPIServiceFixture())
        client = fixture.flask_app.test_client()
        resp = client.get('/flagged')

        self.assertThat(resp, IsResponse("Flagged version 1.3"))

    def test_can_select_flagged_view(self):
        fixture = self.useFixture(SimpleAPIServiceFixture())
        client = fixture.flask_app.test_client()
        resp = client.get(
            '/flagged',
            headers={'Accept': 'application/vnd.vendor.1.4+feature1'})

        self.assertThat(resp, IsResponse("Flagged version 1.4 with feature1"))

    def test_no_acceptable_version(self):
        fixture = self.useFixture(SimpleAPIServiceFixture())
        client = fixture.flask_app.test_client()
        resp = client.get(
            '/flagged',
            headers={'Accept': 'application/vnd.vendor.1.0+foo'})

        self.assertThat(
            resp,
            IsResponse(
                Contains(
                    "Could not find view for version '1.0' and flag 'foo'"),
                406))

    def test_view_decorator_works(self):
        fixture = self.useFixture(SimpleAPIServiceFixture())

        new_api = fixture.service.api('/new')

        @new_api.view(introduced_at='1.0')
        def new_view():
            return "new view", 200

        client = fixture.flask_app.test_client()
        resp = client.get('/new')

        self.assertThat(resp, IsResponse("new view"))

        def test_can_reuse_url_with_different_method(self):
            fixture = self.useFixture(SimpleAPIServiceFixture())

            # /foo already exists as a POST endpoint, we should be able to
            # create another /foo API with a GET endpoint.
            foo_get_api = fixture.service.api('/foo', methods=['GET'])

            @foo_get_api.view(introduced_at='1.0')
            def get_foo():
                return "Foo GET API"

            client = fixture.app.test_client()
            resp_get = client.get('/foo')

            self.assertThat(resp_get, IsResponse("Foo GET API"))


class EndpointMapTestCase(TestCase):

    def test_simple_match(self):
        # Test an exact match without flags
        m = EndpointMap()
        view = object()

        m.add_view('1.0', None, view)

        self.assertEqual(view, m.get_view('1.0'))

    def test_version_downgrade(self):
        # If we can't satisfy the version requirement we'll return an
        # older view.
        m = EndpointMap()
        view = object()

        m.add_view('1.2', None, view)

        self.assertEqual(view, m.get_view('1.3'))

    def test_flagged_view(self):
        # Test an exact match with flags:
        m = EndpointMap()
        normal_view = object()
        flagged_view = object()

        m.add_view('1.0', None, normal_view)
        m.add_view('1.0', 'flag', flagged_view)

        self.assertEqual(normal_view, m.get_view('1.0'))
        self.assertEqual(flagged_view, m.get_view('1.0', 'flag'))

    def test_flagged_downgrade(self):
        # If we can't satisfy the flag request we'll ignore it:
        m = EndpointMap()
        normal_view = object()

        m.add_view('1.0', None, normal_view)

        self.assertEqual(normal_view, m.get_view('1.0', 'flag'))

    def test_does_not_version_upgrade(self):
        # if we can't satisfy the version request we won't upgrade to
        # an older version
        m = EndpointMap()
        view = object()

        m.add_view('1.2', None, view)

        self.assertEqual(None, m.get_view('1.1'))

    def test_version_downgrade_is_smallest_increment(self):
        # If we can't satisfy the exact version requested, give the
        # client the smallest decrement in version possible.
        m = EndpointMap()
        view11 = object()
        view12 = object()
        view13 = object()

        m.add_view('1.1', None, view11)
        m.add_view('1.2', None, view12)
        m.add_view('1.3', None, view13)

        self.assertEqual(view13, m.get_view('1.4'))


class EndpointMapTypeCheckingTests(TestWithScenarios):

    scenarios = [
        ('bad version type', {
            'args': (True, None, None),
            'exception': TypeError,
            'expected_error': "Version must be a string, not bool",
        }),
        ('bad flag type', {
            'args': ('1.0', object(), None),
            'exception': TypeError,
            'expected_error': "Flag must be a string or None, not object",
        }),
        ('version with too many components', {
            'args': ('1.0.0', None, None),
            'exception': ValueError,
            'expected_error': "Version must be in the format "
                              "<major>.<minor>",
        }),
        ('bad major version', {
            'args': ('one.2', None, None),
            'exception': ValueError,
            'expected_error': "Major version number is not an integer",
        }),
        ('bad minor version', {
            'args': ('1.two', None, None),
            'exception': ValueError,
            'expected_error': "Minor version number is not an integer",
        }),
    ]

    def test_add_view_type_checking(self):
        m = EndpointMap()
        self.assertRaisesRegex(
            self.exception,
            self.expected_error,
            methodcaller('add_view', *self.args),
            m
        )

    def test_get_view_type_checking(self):
        # get view doesn't accept the view parameter, so trim it from the
        # argument list:
        args = self.args[:-1]
        m = EndpointMap()
        self.assertRaisesRegex(
            self.exception,
            self.expected_error,
            methodcaller('get_view', *args),
            m
        )


class AcceptHeaderParseTests(TestWithScenarios):

    scenarios = [
        ('No match', {
            'vendor': '',
            'headers': ['*/*'],
            'expected': (None, None),
        }),
        ('Mismatched vendor', {
            'vendor': 'foo',
            'headers': ['application/vnd.bar.1.2'],
            'expected': (None, None),
        }),
        ('Normal mimetype', {
            'vendor': 'foo',
            'headers': ['text/html'],
            'expected': (None, None),
        }),
        ('invalid version format', {
            'vendor': 'foo',
            'headers': ['application/vnd.foo.version1'],
            'expected': (None, None),
        }),
        ('Version with no flag', {
            'vendor': 'foo',
            'headers': ['application/vnd.foo.1.2'],
            'expected': ('1.2', None),
        }),
        ('Version with flag', {
            'vendor': 'foo',
            'headers': ['application/vnd.foo.1.3+feature1'],
            'expected': ('1.3', 'feature1'),
        }),
        ('match after normal mimetype', {
            'vendor': 'foo',
            'headers': ['text/html', 'application/vnd.foo.1.3+feature1'],
            'expected': ('1.3', 'feature1'),
        }),
        ('match after vendor mismatch mimetype', {
            'vendor': 'foo',
            'headers': ['application/vnd.bar.1.2',
                        'application/vnd.foo.1.3+feature1'],
            'expected': ('1.3', 'feature1'),
        }),
    ]

    def test_header_parsing(self):
        observed = parse_accept_headers(self.vendor, self.headers)
        self.assertEqual(observed, self.expected)


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
