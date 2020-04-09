from __future__ import unicode_literals
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).
import testtools

from acceptable import get_metadata
from acceptable.tests.test_main import TemporaryModuleFixture
from acceptable.__main__ import import_metadata

from acceptable import lint


class LintTestCase(testtools.TestCase):

    def get_metadata(self, code='', module='service', locations=True):
        fixture = self.useFixture(TemporaryModuleFixture(module, code))
        import_metadata([module])
        metadata, locations = get_metadata().serialize()
        return metadata, locations, fixture.path


class LintTests(LintTestCase):
    def test_not_modify(self):
        metadata, locations, path = self.get_metadata("""
            from acceptable import *
            service = AcceptableService('myservice', 'group')
            api = service.api('/', 'api')

            @api
            def view():
                "Docs"
        """)

        self.assertIn('$version', metadata)
        orig = metadata.copy()
        list(lint.metadata_lint(metadata, metadata, locations))
        self.assertEqual(metadata, orig)

    def test_missing_api_documentation(self):
        metadata, locations, path = self.get_metadata("""
            from acceptable import *
            service = AcceptableService('myservice', 'group')
            api = service.api('/', 'api', introduced_at=1)

            @api
            def view():
                pass
        """)

        msgs = list(lint.metadata_lint(metadata, metadata, locations))
        self.assertEqual(msgs[0].level, lint.WARNING)
        self.assertEqual('doc', msgs[0].name),
        self.assertEqual('api', msgs[0].api_name),
        self.assertEqual(msgs[0].location['filename'], path)
        self.assertEqual(msgs[0].location['lineno'], 6)

        # test with new api
        msgs = list(lint.metadata_lint({}, metadata, locations))
        self.assertEqual(msgs[0].level, lint.ERROR)
        self.assertEqual('doc', msgs[0].name),
        self.assertEqual('api', msgs[0].api_name),
        self.assertEqual(msgs[0].location['filename'], path)
        self.assertEqual(msgs[0].location['lineno'], 6)

    def test_missing_introduced_at(self):
        metadata, locations, path = self.get_metadata("""
            from acceptable import *
            service = AcceptableService('myservice', 'group')
            api = service.api('/', 'api')

            @api
            def view():
                "Docs"
        """)

        msgs = list(lint.metadata_lint({}, metadata, locations))
        self.assertEqual(msgs[0].level, lint.ERROR)
        self.assertEqual('introduced_at', msgs[0].name),
        self.assertEqual('api', msgs[0].api_name),
        self.assertEqual(msgs[0].location['filename'], path)
        self.assertEqual(msgs[0].location['lineno'], 3)

    def test_changed_introduced_at(self):
        old, _, _ = self.get_metadata(module='old', code="""
            from acceptable import *
            service = AcceptableService('myservice', 'group')
            api = service.api('/', 'api', introduced_at=1)

            @api
            def view():
                "Docs"
        """)

        new, locations, _ = self.get_metadata(module='new', code="""
            from acceptable import *
            service = AcceptableService('myservice', 'group')
            api = service.api('/', 'api', introduced_at=2)

            @api
            def view():
                "Docs"
        """)

        msgs = list(lint.metadata_lint(old, new, locations))
        self.assertEqual(msgs[0].level, lint.ERROR)
        self.assertEqual('introduced_at', msgs[0].name)
        self.assertIn('changed from 1 to 2', msgs[0].msg)

        # new api shouldn't warn about introduced at
        msgs = list(lint.metadata_lint({}, new, locations))
        self.assertEqual(0, len(msgs))

    def test_method_added_is_ok(self):
        old, _, _ = self.get_metadata(module='old', code="""
            from acceptable import *
            service = AcceptableService('myservice', 'group')
            api = service.api('/', 'api', introduced_at=1)

            @api
            def view():
                "Docs"
        """)

        new, locations, _ = self.get_metadata(module='new', code="""
            from acceptable import *
            service = AcceptableService('myservice', 'group')
            api = service.api(
                '/', 'api', introduced_at=1, methods=['GET', 'POST'])

            @api
            def view():
                "Docs"
        """)

        self.assertEqual([], list(lint.metadata_lint(old, new, locations)))

    def test_method_removed_is_error(self):
        old, _, _ = self.get_metadata(module='old', code="""
            from acceptable import *
            service = AcceptableService('myservice', 'group')
            api = service.api('/', 'api', introduced_at=1)

            @api
            def view():
                "Docs"
        """)

        new, locations, _ = self.get_metadata(module='new', code="""
            from acceptable import *
            service = AcceptableService('myservice', 'group')
            api = service.api(
                '/', 'api', introduced_at=1, methods=['POST'])

            @api
            def view():
                "Docs"
        """)

        msgs = list(lint.metadata_lint(old, new, locations))
        self.assertEqual(msgs[0].level, lint.ERROR)
        self.assertEqual('methods', msgs[0].name)
        self.assertIn('GET removed', msgs[0].msg)

    def test_url_changed_is_error(self):
        old, _, _ = self.get_metadata(module='old', code="""
            from acceptable import *
            service = AcceptableService('myservice', 'group')
            api = service.api('/', 'api', introduced_at=1)

            @api
            def view():
                "Docs"
        """)

        new, locations, _ = self.get_metadata(module='new', code="""
            from acceptable import *
            service = AcceptableService('myservice', 'group')
            api = service.api('/other', 'api', introduced_at=1)

            @api
            def view():
                "Docs"
        """)

        msgs = list(lint.metadata_lint(old, new, locations))
        self.assertEqual(msgs[0].level, lint.ERROR)
        self.assertEqual('url', msgs[0].name)
        self.assertIn('/other', msgs[0].msg)

    def test_required_on_new_api_ok(self):
        old, _, _ = self.get_metadata(module='old', code="""
            from acceptable import *
            service = AcceptableService('myservice', 'group')
        """)

        new, locations, _ = self.get_metadata(module='new', code="""
            from acceptable import *
            service = AcceptableService('myservice', 'group')
            api = service.api('/other', 'api', introduced_at=1)
            api.request_schema = {
                'type': 'object',
                'properties': {
                    'context': {'type': 'string', 'description': 'Context'}
                },
                'required': ['context']
            }

            @api
            def view():
                "Docs"
        """)
        self.assertEqual(
            [],
            [str(i) for i in lint.metadata_lint(old, new, locations)]
        )

    def test_required_on_existing_api_is_error(self):
        old, _, _ = self.get_metadata(module='old', code="""
            from acceptable import *
            service = AcceptableService('myservice', 'group')

            api = service.api('/other', 'api', introduced_at=1)

            @api
            def view():
                "Docs"
        """)

        new, locations, _ = self.get_metadata(module='new', code="""
            from acceptable import *
            service = AcceptableService('myservice', 'group')
            api = service.api('/other', 'api', introduced_at=1)
            api.request_schema = {
                'type': 'object',
                'properties': {
                    'context': {
                        'type': 'string',
                        'introduced_at': 2,
                        'description': 'Context'
                    }
                },
                'required': ['context']
            }
            api.changelog(2, 'Added context field')

            @api
            def view():
                "Docs"
        """)
        self.assertEqual(
            ['Cannot require new field context'],
            [i.msg for i in lint.metadata_lint(old, new, locations)]
        )

    def test_schema_removed_is_error(self):
        old, _, _ = self.get_metadata(module='old', code="""
            from acceptable import *
            service = AcceptableService('myservice', 'group')
            api = service.api('/other', 'api', introduced_at=1)
            api.request_schema = {
                'type': 'object',
                'properties': {
                    'context': {'type': 'string', 'description': 'Context'}
                },
                'required': ['context']
            }

            @api
            def view():
                "Docs"
        """)

        new, locations, _ = self.get_metadata(module='new', code="""
            from acceptable import *
            service = AcceptableService('myservice', 'group')
            api = service.api('/other', 'api', introduced_at=1)

            @api
            def view():
                "Docs"
        """)
        self.assertEqual(
            ['Request schema removed'],
            [i.msg for i in lint.metadata_lint(old, new, locations)]
        )

class WalkSchemaTests(LintTestCase):

    def test_type_changed_is_error(self):
        old = {'type': 'string'}
        new = {'type': 'object'}

        msgs = list(lint.walk_schema('name', old, new, root=True))
        self.assertEqual(1, len(msgs))
        self.assertEqual(msgs[0].level, lint.ERROR)
        self.assertEqual('name.type', msgs[0].name)
        self.assertIn('remove type string', msgs[0].msg)

    def test_type_changed_is_error_multiple_types(self):
        old = {'type': ['string', 'object']}
        new = {'type': 'object'}

        msgs = list(lint.walk_schema('name', old, new, root=True))
        self.assertEqual(1, len(msgs))
        self.assertEqual(msgs[0].level, lint.ERROR)
        self.assertEqual('name.type', msgs[0].name)
        self.assertIn('remove type string', msgs[0].msg)

    def test_added_required_is_error(self):
        old = {
            'type': 'object',
            'required': ['foo'],
            'properties': {
                'foo': {
                    'type': 'string',
                    'description': 'description',
                    'introduced_at': 1,
                },
                'bar': {
                    'type': 'string',
                    'description': 'description',
                    'introduced_at': 1,
                },
            }
        }
        new = {
            'type': 'object',
            'required': ['foo', 'bar'],
            'properties': {
                'foo': {
                    'type': 'string',
                    'description': 'description',
                    'introduced_at': 1,
                },
                'bar': {
                    'type': 'string',
                    'description': 'description',
                    'introduced_at': 1,
                },
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
                'foo': {
                    'type': 'string',
                    'description': 'description',
                    'introduced_at': 1,
                },
            }
        }

        msgs = list(lint.walk_schema('name', old, new, root=True))
        self.assertEqual(2, len(msgs))
        self.assertEqual(msgs[0].level, lint.ERROR)
        self.assertEqual('name.bar', msgs[0].name)

        self.assertIsInstance(msgs[1], lint.CheckChangelog)

    def test_missing_doc_and_introduced_when_adding_new_field(self):
        old = {
            'type': 'object',
        }

        new = {
            'type': 'object',
            'properties': {
                'foo': {'type': 'object'},
            },
        }
        msgs = list(lint.walk_schema('name', old, new, root=True))
        self.assertEqual(2, len(msgs))

        self.assertEqual(msgs[0].level, lint.WARNING)
        self.assertEqual('name.foo.description', msgs[0].name)
        self.assertIn('missing', msgs[0].msg)

        self.assertEqual(msgs[1].level, lint.DOCUMENTATION)
        self.assertEqual('name.foo.introduced_at', msgs[1].name)
        self.assertIn('missing', msgs[1].msg)

    def test_no_introduced_at_when_present_in_old(self):
        old = {
            'type': 'object',
            'properties': {
                'foo': {'type': 'object'},
            },
        }

        new = {
            'type': 'object',
            'properties': {
                'foo': {'type': 'object', 'description': 'description'},
            },
        }
        msgs = list(lint.walk_schema('name', old, new, root=True))
        self.assertEqual(0, len(msgs))

    def test_missing_introduced_at_skipped_if_new_api(self):
        old = {
            'type': 'object',
        }

        new = {
            'type': 'object',
            'properties': {
                'foo': {'type': 'object'},
            },
        }

        msgs = list(lint.walk_schema(
            'name', old, new, root=True, new_api=True
        ))
        self.assertEqual(1, len(msgs))
        self.assertEqual(msgs[0].level, lint.WARNING)
        self.assertEqual('name.foo.description', msgs[0].name)
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
                            'description': 'description',
                            'introduced_at': 2,
                        },
                    },
                },
            },
        }
        new = {
            'type': 'object',
            'properties': {
                'foo': {
                    'description': 'description',
                    'type': 'object',
                    'required': ['bar', 'foo'],  # error for required change
                    'properties': {
                        'bar': {
                            'type': 'object',  # type changed
                            'description': 'description'
                        },
                        'baz': {
                            'type': 'string',
                            'description': 'description',
                            'introduced_at': 3,  # changed
                        },
                    },
                },
            },
        }

        msgs = list(lint.walk_schema('name', old, new, root=True))
        self.assertEqual(3, len(msgs))

        self.assertEqual(msgs[0].level, lint.ERROR)
        self.assertEqual('name.foo.required', msgs[0].name)

        self.assertEqual(msgs[1].level, lint.ERROR)
        self.assertEqual('name.foo.bar.type', msgs[1].name)

        self.assertEqual(msgs[2].level, lint.ERROR)
        self.assertEqual('name.foo.baz.introduced_at', msgs[2].name)

    def test_arrays(self):
        old = {
            'type': 'array',
            'items': {
                'description': 'description',
                'type': 'object',
                'properties': {
                    'foo': {'type': 'object', 'description': 'description'},
                },
            },
        }
        new = {
            'type': 'array',
            'items': {
                'description': 'description',
                'type': 'object',
                'properties': {
                    'foo': {'type': 'object', 'description': 'description'},
                    'bar': {'type': 'object'},
                },
            },
        }

        msgs = list(lint.walk_schema('name', old, new, root=True))

        self.assertEqual(2, len(msgs))

        self.assertEqual(msgs[0].level, lint.WARNING)
        self.assertEqual('name.items.bar.description', msgs[0].name)

        self.assertEqual(msgs[1].level, lint.DOCUMENTATION)
        self.assertEqual('name.items.bar.introduced_at', msgs[1].name)

    def test_new_api_introduced_at_enforced(self):
        old, _, _ = self.get_metadata(module='old', code="""
            from acceptable import AcceptableService
            service = AcceptableService('myservice', 'group')
            api1 = service.api('/api1', 'api1', introduced_at=1)
            @api1
            def view():
                "Docs"
        """)

        new, locations, _ = self.get_metadata(module='new', code="""
            from acceptable import AcceptableService
            service = AcceptableService('myservice', 'group')
            api1 = service.api('/api1', 'api1', introduced_at=1)
            @api1
            def view1():
                "Docs"

            api2 = service.api('/api2', 'api2', introduced_at=1)
            @api2
            def view2():
                "Docs"
        """)
        self.assertEqual(
            ['introduced_at should be > 1'],
            [i.msg for i in lint.metadata_lint(old, new, locations)]
        )

    def test_new_api_introduced_at_is_int(self):
        old, _, _ = self.get_metadata(module='old', code="""
            from acceptable import AcceptableService
            service = AcceptableService('myservice', 'group')
        """)

        new, locations, _ = self.get_metadata(module='new', code="""
            from acceptable import AcceptableService
            service = AcceptableService('myservice', 'group')
            api1 = service.api('/api1', 'api1', introduced_at="1")
            @api1
            def view1():
                "Docs"
        """)
        self.assertEqual(
            ['introduced_at should be an integer'],
            [i.msg for i in lint.metadata_lint(old, new, locations)]
        )
