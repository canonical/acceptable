# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).
import testtools
from acceptable.tests.test_main import TemporaryModuleFixture
from acceptable.__main__ import import_metadata

from acceptable import lint


class LintTestCase(testtools.TestCase):

    def get_metadata(self, code='', module='service', locations=True):
        fixture = self.useFixture(TemporaryModuleFixture(module, code))
        metadata = import_metadata([module], locations=locations)
        return metadata, fixture.path


class LintTests(LintTestCase):
    def test_missing_api_documentation(self):
        metadata, path = self.get_metadata("""
            from acceptable import *
            service = AcceptableService('myservice', 'group')
            api = service.api('/', 'api', introduced_at=1)

            @api
            def view():
                pass
        """)

        msgs = list(lint.metadata_lint(metadata, metadata))
        self.assertIsInstance(msgs[0], lint.Warning)
        self.assertEqual('doc', msgs[0].name),
        self.assertEqual('api', msgs[0].api_name),
        self.assertEqual(
            {'filename': path, 'lineno': 3},
            msgs[0].location,
        )

        # test with new api
        msgs = list(lint.metadata_lint({}, metadata))
        self.assertIsInstance(msgs[0], lint.Error)
        self.assertEqual('doc', msgs[0].name),
        self.assertEqual('api', msgs[0].api_name),
        self.assertEqual(
            {'filename': path, 'lineno': 3},
            msgs[0].location,
        )

    def test_missing_introduced_at(self):
        metadata, path = self.get_metadata("""
            from acceptable import *
            service = AcceptableService('myservice', 'group')
            api = service.api('/', 'api')

            @api
            def view():
                "Docs"
        """)

        msgs = list(lint.metadata_lint({}, metadata))
        self.assertIsInstance(msgs[0], lint.Error)
        self.assertEqual('introduced_at', msgs[0].name),
        self.assertEqual('api', msgs[0].api_name),
        self.assertEqual(
            {'filename': path, 'lineno': 3},
            msgs[0].location,
        )

    def test_changed_introduced_at(self):
        old, _ = self.get_metadata(module='old', code="""
            from acceptable import *
            service = AcceptableService('myservice', 'group')
            api = service.api('/', 'api', introduced_at=1)

            @api
            def view():
                "Docs"
        """)

        new, _ = self.get_metadata(module='new', code="""
            from acceptable import *
            service = AcceptableService('myservice', 'group')
            api = service.api('/', 'api', introduced_at=2)

            @api
            def view():
                "Docs"
        """)

        msgs = list(lint.metadata_lint(old, new))
        self.assertIsInstance(msgs[0], lint.Error)
        self.assertEqual('introduced_at', msgs[0].name)
        self.assertIn('changed from 1 to 2', msgs[0].msg)

        # new api shouldn't warn about introduced at
        msgs = list(lint.metadata_lint({}, new))
        self.assertEqual(0, len(msgs))

    def test_method_added_is_ok(self):
        old, _ = self.get_metadata(module='old', code="""
            from acceptable import *
            service = AcceptableService('myservice', 'group')
            api = service.api('/', 'api', introduced_at=1)

            @api
            def view():
                "Docs"
        """)

        new, _ = self.get_metadata(module='new', code="""
            from acceptable import *
            service = AcceptableService('myservice', 'group')
            api = service.api(
                '/', 'api', introduced_at=1, methods=['GET', 'POST'])

            @api
            def view():
                "Docs"
        """)

        self.assertEqual([], list(lint.metadata_lint(old, new)))

    def test_method_removed_is_error(self):
        old, _ = self.get_metadata(module='old', code="""
            from acceptable import *
            service = AcceptableService('myservice', 'group')
            api = service.api('/', 'api', introduced_at=1)

            @api
            def view():
                "Docs"
        """)

        new, _ = self.get_metadata(module='new', code="""
            from acceptable import *
            service = AcceptableService('myservice', 'group')
            api = service.api(
                '/', 'api', introduced_at=1, methods=['POST'])

            @api
            def view():
                "Docs"
        """)

        msgs = list(lint.metadata_lint(old, new))
        self.assertIsInstance(msgs[0], lint.Error)
        self.assertEqual('methods', msgs[0].name)
        self.assertIn('GET removed', msgs[0].msg)

    def test_url_changed_is_error(self):
        old, _ = self.get_metadata(module='old', code="""
            from acceptable import *
            service = AcceptableService('myservice', 'group')
            api = service.api('/', 'api', introduced_at=1)

            @api
            def view():
                "Docs"
        """)

        new, _ = self.get_metadata(module='new', code="""
            from acceptable import *
            service = AcceptableService('myservice', 'group')
            api = service.api('/other', 'api', introduced_at=1)

            @api
            def view():
                "Docs"
        """)

        msgs = list(lint.metadata_lint(old, new))
        self.assertIsInstance(msgs[0], lint.Error)
        self.assertEqual('url', msgs[0].name)
        self.assertIn('/other', msgs[0].msg)


class WalkSchemaTests(LintTestCase):

    def test_type_changed_is_error(self):
        old = {'type': 'string'}
        new = {'type': 'object'}

        msgs = list(lint.walk_schema('name', old, new, root=True))
        self.assertEqual(1, len(msgs))
        self.assertIsInstance(msgs[0], lint.Error)
        self.assertEqual('name.type', msgs[0].name)
        self.assertIn('remove type string', msgs[0].msg)

    def test_type_changed_is_error_multiple_types(self):
        old = {'type': ['string', 'object']}
        new = {'type': 'object'}

        msgs = list(lint.walk_schema('name', old, new, root=True))
        self.assertEqual(1, len(msgs))
        self.assertIsInstance(msgs[0], lint.Error)
        self.assertEqual('name.type', msgs[0].name)
        self.assertIn('remove type string', msgs[0].msg)

    def test_added_required_is_error(self):
        old = {
            'type': 'object',
            'required': ['foo'],
            'properties': {
                'foo': {'type': 'string', 'doc': 'doc', 'introduced_at': 1},
                'bar': {'type': 'string', 'doc': 'doc', 'introduced_at': 1},
            }
        }
        new = {
            'type': 'object',
            'required': ['foo', 'bar'],
            'properties': {
                'foo': {'type': 'string', 'doc': 'doc', 'introduced_at': 1},
                'bar': {'type': 'string', 'doc': 'doc', 'introduced_at': 1},
            }
        }
        msgs = list(lint.walk_schema('name', old, new, root=True))
        self.assertEqual(3, len(msgs))
        self.assertEqual('name.required', msgs[0].name)
        self.assertIn('bar', msgs[0].msg)

        self.assertIsInstance(msgs[1], lint.CheckChangelog)
        self.assertIsInstance(msgs[2], lint.CheckChangelog)

    def test_delete_property_is_error(self):
        old = {
            'type': 'object',
            'properties': {
                'foo': {'type': 'string'},
                'bar': {'type': 'string'},
            }
        }
        new = {
            'type': 'object',
            'properties': {
                'foo': {'type': 'string', 'doc': 'doc', 'introduced_at': 1},
            }
        }

        msgs = list(lint.walk_schema('name', old, new, root=True))
        self.assertEqual(2, len(msgs))
        self.assertIsInstance(msgs[0], lint.Error)
        self.assertEqual('name.bar', msgs[0].name)

        self.assertIsInstance(msgs[1], lint.CheckChangelog)

    def test_missing_doc_and_introduced_at_is_warning(self):
        msgs = list(lint.walk_schema('name', {}, {}))
        self.assertEqual(2, len(msgs))

        self.assertIsInstance(msgs[0], lint.Warning)
        self.assertEqual('name.doc', msgs[0].name)
        self.assertIn('missing', msgs[0].msg)

        self.assertIsInstance(msgs[1], lint.Warning)
        self.assertEqual('name.introduced_at', msgs[1].name)
        self.assertIn('missing', msgs[1].msg)

    def test_missing_introduced_at_skipped_if_new_api(self):
        msgs = list(lint.walk_schema('name', {}, {}, new_api=True))
        self.assertEqual(1, len(msgs))
        self.assertIsInstance(msgs[0], lint.Warning)
        self.assertEqual('name.doc', msgs[0].name)
        self.assertIn('missing', msgs[0].msg)

    def test_nested_objects(self):
        old = {
            'type': 'object',
            'properties': {
                'foo': {
                    'type': 'object',
                    'required': ['bar'],
                    'properties': {
                        'bar': {'type': 'string'},
                        'baz': {
                            'type': 'string',
                            'doc': 'doc',
                            'introduced_at': 2,
                        },
                    },
                },
            },
        }
        new = {
            'type': 'object',
            'properties': {
                'foo': {  # warning for no introduced_at
                    'doc': 'doc',
                    'type': 'object',
                    'required': ['bar', 'foo'],  # error for required change
                    'properties': {
                        'bar': {
                            'type': 'object',  # type changed
                            'doc': 'doc',  # introduced_at warning
                        },
                        'baz': {
                            'type': 'string',
                            'doc': 'doc',
                            'introduced_at': 3,  # changed
                        },
                    },
                },
            },
        }

        msgs = list(lint.walk_schema('name', old, new, root=True))
        self.assertEqual(5, len(msgs))

        self.assertIsInstance(msgs[0], lint.Warning)
        self.assertEqual('name.foo.introduced_at', msgs[0].name)

        self.assertIsInstance(msgs[1], lint.Error)
        self.assertEqual('name.foo.required', msgs[1].name)

        self.assertIsInstance(msgs[2], lint.Warning)
        self.assertEqual('name.foo.bar.introduced_at', msgs[2].name)

        self.assertIsInstance(msgs[3], lint.Error)
        self.assertEqual('name.foo.bar.type', msgs[3].name)

        self.assertIsInstance(msgs[4], lint.Error)
        self.assertEqual('name.foo.baz.introduced_at', msgs[4].name)
