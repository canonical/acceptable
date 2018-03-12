# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).
import ast
import argparse
import os.path
import sys
from textwrap import dedent

import fixtures
from testtools import TestCase
from testtools.matchers import (
    Contains
)

from acceptable import _build_doubles


class ExtractSchemasFromSourceTests(TestCase):

    def test_invalid_source(self):
        self.assertRaises(
            SyntaxError,
            _build_doubles.extract_schemas_from_source,
            "This is not valid python source!"
        )

    def test_returns_empty_list_on_empty_source(self):
        self.assertEqual([], _build_doubles.extract_schemas_from_source(''))

    def test_ignores_undecorated_functions(self):
        observed = _build_doubles.extract_schemas_from_source(
            dedent('''
            def my_view():
                pass
            '''))
        self.assertEqual([], observed)

    def test_can_extract_acceptable_view(self):
        [schema] = _build_doubles.extract_schemas_from_source(
            dedent('''

            service = AcceptableService('vendor')

            root_api = service.api('/', 'root')

            @root_api.view(introduced_at='1.0')
            def my_view():
                pass
            '''))

        self.assertEqual('root', schema.view_name)
        self.assertEqual('/', schema.url)
        self.assertEqual('1.0', schema.version)
        self.assertEqual(['GET'], schema.methods)
        self.assertEqual(None, schema.input_schema)
        self.assertEqual(None, schema.output_schema)

    def test_can_extract_schema_with_input_schema(self):
        [schema] = _build_doubles.extract_schemas_from_source(
            dedent('''

            service = AcceptableService('vendor')

            root_api = service.api('/', 'root')

            @root_api.view(introduced_at='1.0')
            @validate_body({'type': 'object'})
            def my_view():
                pass
            '''))

        self.assertEqual('root', schema.view_name)
        self.assertEqual('/', schema.url)
        self.assertEqual('1.0', schema.version)
        self.assertEqual(['GET'], schema.methods)
        self.assertEqual({'type': 'object'}, schema.input_schema)
        self.assertEqual(None, schema.output_schema)

    def test_can_extract_schema_with_output_schema(self):
        [schema] = _build_doubles.extract_schemas_from_source(
            dedent('''

            service = AcceptableService('vendor')

            root_api = service.api('/', 'root')

            @root_api.view(introduced_at='1.0')
            @validate_output({'type': 'object'})
            def my_view():
                pass
            '''))

        self.assertEqual('root', schema.view_name)
        self.assertEqual('/', schema.url)
        self.assertEqual('1.0', schema.version)
        self.assertEqual(['GET'], schema.methods)
        self.assertEqual(None, schema.input_schema)
        self.assertEqual({'type': 'object'}, schema.output_schema)

    def test_can_extract_schema_with_methods(self):
        [schema] = _build_doubles.extract_schemas_from_source(
            dedent('''

            service = AcceptableService('vendor')

            root_api = service.api('/', 'root', methods=['POST', 'PUT'])

            @root_api.view(introduced_at='1.0')
            def my_view():
                pass
            '''))

        self.assertEqual('root', schema.view_name)
        self.assertEqual('/', schema.url)
        self.assertEqual('1.0', schema.version)
        self.assertEqual(['POST', 'PUT'], schema.methods)
        self.assertEqual(None, schema.input_schema)
        self.assertEqual(None, schema.output_schema)

    def test_url_can_be_specified_with_kwarg(self):
        [schema] = _build_doubles.extract_schemas_from_source(
            dedent('''

            service = AcceptableService('vendor')

            root_api = service.api(url='/foo', view_name='root')

            @root_api.view(introduced_at='1.0')
            def my_view():
                pass
            '''))

        self.assertEqual('root', schema.view_name)
        self.assertEqual('/foo', schema.url)
        self.assertEqual('1.0', schema.version)
        self.assertEqual(['GET'], schema.methods)
        self.assertEqual(None, schema.input_schema)
        self.assertEqual(None, schema.output_schema)

    def test_can_extract_version_with_kwarg(self):
        [schema] = _build_doubles.extract_schemas_from_source(
            dedent('''

            service = AcceptableService('vendor')

            root_api = service.api('/foo', 'root')

            @root_api.view(introduced_at='1.1')
            def my_view():
                pass
            '''))

        self.assertEqual('root', schema.view_name)
        self.assertEqual('/foo', schema.url)
        self.assertEqual('1.1', schema.version)
        self.assertEqual(['GET'], schema.methods)
        self.assertEqual(None, schema.input_schema)
        self.assertEqual(None, schema.output_schema)

    def test_can_extract_multiple_versioned_schemas(self):
        [schema1, schema2] = _build_doubles.extract_schemas_from_source(
            dedent('''

            service = AcceptableService('vendor')

            root_api = service.api('/foo', 'root')

            @root_api.view(introduced_at='1.1')
            def my_view():
                pass


            @root_api.view(introduced_at='1.2')
            def my_view():
                pass
            '''))

        self.assertEqual('1.1', schema1.version)

    def test_can_extract_multiple_names_for_one_view(self):
        # This is helpful when in the process of renaming a view.
        [schema1, schema2] = _build_doubles.extract_schemas_from_source(
            dedent('''

            service = AcceptableService('vendor')

            old_api = service.api('/old', 'old')
            new_api = service.api('/new', 'new')

            @old_api.view(introduced_at='1.0')
            @new_api.view(introduced_at='1.0')
            @validate_body({'type': 'object'})
            @validate_output({'type': 'array'})
            def my_view():
                pass
            '''))

        self.assertEqual('old', schema1.view_name)
        self.assertEqual('/old', schema1.url)
        self.assertEqual('1.0', schema1.version)
        self.assertEqual(['GET'], schema1.methods)
        self.assertEqual({'type': 'object'}, schema1.input_schema)
        self.assertEqual({'type': 'array'}, schema1.output_schema)
        self.assertEqual('new', schema2.view_name)
        self.assertEqual('/new', schema2.url)
        self.assertEqual('1.0', schema2.version)
        self.assertEqual(['GET'], schema2.methods)
        self.assertEqual({'type': 'object'}, schema2.input_schema)
        self.assertEqual({'type': 'array'}, schema2.output_schema)

    def test_can_specify_version_as_arg(self):
        [schema] = _build_doubles.extract_schemas_from_source(
            dedent('''

            service = AcceptableService('vendor')

            root_api = service.api('/foo', 'root')

            @root_api.view('1.5')
            def my_view():
                pass
            '''))

        self.assertEqual('1.5', schema.version)

    def test_handles_other_assignments(self):
        self.assertEqual(
            [], _build_doubles.extract_schemas_from_source('foo = {}'))


class ExtractSchemasFromFileTests(TestCase):

    def test_logs_on_missing_file(self):
        workdir = self.useFixture(fixtures.TempDir())
        fake_logger = self.useFixture(fixtures.FakeLogger())

        bad_path = os.path.join(workdir.path, 'path_does_not_exist')
        result = _build_doubles.extract_schemas_from_file(bad_path)

        self.assertIsNone(result)
        self.assertThat(
            fake_logger.output,
            Contains('Extracting schemas from %s' % bad_path))
        self.assertThat(
            fake_logger.output,
            Contains('Cannot extract schemas: No such file or directory'))

    def test_logs_on_no_permissions(self):
        workdir = self.useFixture(fixtures.TempDir())
        fake_logger = self.useFixture(fixtures.FakeLogger())

        bad_path = os.path.join(workdir.path, 'path_not_readable')
        with open(bad_path, 'w') as f:
            f.write("# You can't read me")
        os.chmod(bad_path, 0)
        result = _build_doubles.extract_schemas_from_file(bad_path)

        self.assertIsNone(result)
        self.assertThat(
            fake_logger.output,
            Contains('Extracting schemas from %s' % bad_path))
        self.assertThat(
            fake_logger.output,
            Contains('Cannot extract schemas: Permission denied'))

    def test_logs_on_syntax_error(self):
        workdir = self.useFixture(fixtures.TempDir())
        fake_logger = self.useFixture(fixtures.FakeLogger())

        bad_path = os.path.join(workdir.path, 'foo.py')
        with open(bad_path, 'w') as f:
            f.write("not valid pyton")

        result = _build_doubles.extract_schemas_from_file(bad_path)

        self.assertIsNone(result)
        self.assertThat(
            fake_logger.output,
            Contains('Extracting schemas from %s' % bad_path))
        self.assertThat(
            fake_logger.output,
            Contains('Cannot extract schemas: invalid syntax (foo.py, line 1)')
        )

    def test_logs_on_schema_extraction(self):
        workdir = self.useFixture(fixtures.TempDir())
        fake_logger = self.useFixture(fixtures.FakeLogger())

        good_path = os.path.join(workdir.path, 'my.py')
        with open(good_path, 'w') as f:
            f.write(dedent(
                """
                service = AcceptableService('vendor')

                root_api = service.api('/', 'root')

                @root_api.view(introduced_at='1.0')
                def my_view():
                    pass
                """))
        [schema] = _build_doubles.extract_schemas_from_file(good_path)

        self.assertEqual('root', schema.view_name)
        self.assertEqual('1.0', schema.version)
        self.assertEqual(['GET'], schema.methods)
        self.assertEqual(None, schema.input_schema)
        self.assertEqual(None, schema.output_schema)

        self.assertThat(
            fake_logger.output,
            Contains('Extracting schemas from %s' % good_path))
        self.assertThat(
            fake_logger.output,
            Contains('Extracted 1 schema'))


# To support testing, we need a version of ArgumentParser that doesn't call
# sys.exit on error, but rather throws an exception, so we can catch that in
# our tests:
class SaneArgumentParser(argparse.ArgumentParser):

    def error(self, message):
        raise RuntimeError(message)


class ParseArgsTests(TestCase):

    def test_error_with_no_args(self):
        self.assertRaises(
            RuntimeError,
            _build_doubles.parse_args,
            [],
            SaneArgumentParser
        )

    def test_scan_file_requires_file(self):
        self.assertRaises(
            RuntimeError,
            _build_doubles.parse_args,
            ['scan-file'],
            SaneArgumentParser
        )

    def test_can_scan_file(self):
        args = _build_doubles.parse_args(['scan-file', 'some-path'])
        self.assertEqual('some-path', args.file)
        self.assertEqual(_build_doubles.scan_file, args.func)

    def test_build_requires_file(self):
        self.assertRaises(
            RuntimeError,
            _build_doubles.parse_args,
            ['build'],
            SaneArgumentParser
        )

    def test_can_build(self):
        args = _build_doubles.parse_args(['build', 'config-file'])
        self.assertEqual('config-file', args.config_file)
        self.assertEqual(_build_doubles.build_service_doubles, args.func)


class RenderValueTests(TestCase):

    def test_plain(self):
        self.assertEqual("'foo'", _build_doubles.render_value('foo'))

    def test_list(self):
        value = [{'type': 'object', 'properties': {}}, {'type': 'string'}]
        rendered = "[{'properties': {}, 'type': 'object'}, {'type': 'string'}]"
        self.assertEqual(rendered, _build_doubles.render_value(value))

    def test_dict(self):
        value = {
            'type': 'object',
            'properties': {
                'foo': {'type': 'string'},
                'bar': {'type': 'integer'},
            },
            'required': ['foo'],
        }
        rendered = (
            "{"
            "'properties': "
            "{'bar': {'type': 'integer'}, 'foo': {'type': 'string'}}, "
            "'required': ['foo'], "
            "'type': 'object'"
            "}")
        self.assertEqual(rendered, _build_doubles.render_value(value))


class RenderServiceDoubleTests(TestCase):

    def assertIsValidPython(self, source):
        try:
            ast.parse(source)
        except SyntaxError as e:
            self.fail(str(e))

    def test_renders_for_empty_schema_list(self):
        source = _build_doubles.render_service_double(
            'foo', [], 'build config-file')
        self.assertIsValidPython(source)

    def test_renders_for_single_schema(self):
        schema = _build_doubles.ViewSchema(
            view_name='some_view',
            version='1.3',
            input_schema=None,
            output_schema=None,
            methods=['GET'],
            url='/foo',
        )
        source = _build_doubles.render_service_double(
            'foo', [schema], 'build config-file')
        self.assertIsValidPython(source)

    def test_autogenerated_message(self):
        source = _build_doubles.render_service_double(
            'foo', [], 'build config-file')
        self.assertIn(
            "re-generate it by running '%s build config-file'" % (
                os.path.basename(sys.argv[0])),
            source)

    def test_input_and_output_schemas_are_sorted(self):
        schema = _build_doubles.ViewSchema(
            view_name='some_view',
            version='1.3',
            input_schema={
                'type': 'object',
                'properties': {'item': {'type': 'string'}},
            },
            output_schema={
                'type': 'object',
                'properties': {'item': {'type': 'string'}},
            },
            methods=['GET'],
            url='/foo',
        )
        source = _build_doubles.render_service_double(
            'foo', [schema], 'build config-file')
        self.assertIsValidPython(source)
        self.assertIn(
            "input_schema={'properties': {'item': {'type': 'string'}}, "
            "'type': 'object'}", source)
        self.assertIn(
            "output_schema={'properties': {'item': {'type': 'string'}}, "
            "'type': 'object'}", source)
