# -*- coding: utf-8 -*-
# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).

from operator import methodcaller

from testscenarios import TestWithScenarios
from testtools import TestCase

from acceptable import (
    EndpointMap,
    parse_accept_headers,
)


class EndpointMapTestCase(TestCase):

    def test_simple_match(self):
        # Test an exact match without flags
        m = EndpointMap()
        view = object()

        m.add_view('1.0', None, view)

        self.assertEqual(view, m.get_view('1.0'))

    def test_version_upgrade(self):
        # If we can't satisfy the version requirement we'll return a
        # newer view.
        m = EndpointMap()
        view = object()

        m.add_view('1.2', None, view)

        self.assertEqual(view, m.get_view('1.1'))

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

    def test_does_not_version_downgrade(self):
        # if we can't satisfy the version request we won't downgrade to
        # an older version
        m = EndpointMap()
        view = object()

        m.add_view('1.2', None, view)

        self.assertEqual(None, m.get_view('1.3'))

    def test_version_upgrde_is_smallest_increment(self):
        # If we can't satisfy the exact version requested, give the
        # client the smallest increment in version possible.
        m = EndpointMap()
        view11 = object()
        view12 = object()
        view13 = object()

        m.add_view('1.1', None, view11)
        m.add_view('1.2', None, view12)
        m.add_view('1.3', None, view13)

        self.assertEqual(view11, m.get_view('1.0'))


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
            'args': ('one.2', None, None),
            'exception': ValueError,
            'expected_error': "Major version number is not an integer",
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
