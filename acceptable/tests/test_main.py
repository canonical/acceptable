# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).
from __future__ import unicode_literals
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from builtins import str, zip
from future.utils import PY2

import argparse
from collections import OrderedDict
from functools import partial
import io
import json
import os
import subprocess
import tempfile
import yaml

import testtools
import fixtures

from acceptable import __main__ as main
from acceptable import get_metadata
from acceptable.tests._fixtures import (
    CleanUpModuleImport,
    TemporaryModuleFixture,
)


# sys.exit on error, but rather throws an exception, so we can catch that in
# our tests:
class SaneArgumentParser(argparse.ArgumentParser):

    def error(self, message):
        raise RuntimeError(message)


class ParseArgsTests(testtools.TestCase):

    def test_error_with_no_args(self):
        self.assertRaisesRegex(
            RuntimeError,
            'arguments are required' if not PY2 else 'too few arguments',
            main.parse_args,
            [],
            SaneArgumentParser,
        )

    def test_metadata_requires_files(self):
        self.assertRaisesRegex(
            RuntimeError,
            'arguments are required' if not PY2 else 'too few arguments',
            main.parse_args,
            ['metadata'],
            SaneArgumentParser,
        )

    def test_metadata_parses_files(self):
        args = main.parse_args(['metadata', 'foo', 'bar'])
        self.assertEqual(['foo', 'bar'], args.modules)
        self.assertEqual(main.metadata_cmd, args.func)

    def test_render_parses_file(self):
        with tempfile.NamedTemporaryFile('w') as api:
            api.write('hi')
            api.flush()
            args = main.parse_args(['render', '--name=name', api.name])

        self.assertTrue('hi', args.metadata.read())
        self.assertEqual(main.render_cmd, args.func)

        args.metadata.close()  # suppresses ResourceWarning

    def test_render_parses_stdin_with_no_metadata(self):
        stdin = io.StringIO('hi')
        args = main.parse_args(['render', '--name=name'], stdin=stdin)
        self.assertEqual('hi', args.metadata.read())

    def test_lint_reads_file(self):
        with tempfile.NamedTemporaryFile('w') as api:
            api.write('hi')
            api.flush()
            args = main.parse_args(['lint', api.name, 'foo', 'bar'])

        self.assertEqual('hi', args.metadata.read())
        self.assertEqual(args.modules, ['foo', 'bar'])

        args.metadata.close()  # suppresses ResourceWarning

    def test_lint_force_without_update(self):
        with tempfile.NamedTemporaryFile('w') as api:
            api.write('hi')
            api.flush()
            self.assertRaisesRegex(
                RuntimeError,
                '--force can only be used with --update',
                main.parse_args,
                ['lint', api.name, 'foo', '--force'],
                parser_cls=SaneArgumentParser,
            )


class MetadataTests(testtools.TestCase):
    def test_importing_api_metadata_works(self):
        service = """
            from acceptable import AcceptableService
            service = AcceptableService('myservice', 'group')

            root_api = service.api('/', 'root', introduced_at=1)
            root_api.request_schema = {'type': 'object'}
            root_api.response_schema = {'type': 'object'}
            root_api.changelog(4, "changelog")

            @root_api
            def my_view():
                "Documentation."
        """
        fixture = self.useFixture(TemporaryModuleFixture('service', service))
        main.import_metadata(['service'])
        metadata, locations = main.parse(get_metadata())

        self.assertEqual({
            '$version': 4,
            'root': {
                'service': 'myservice',
                'api_group': 'group',
                'api_name': 'root',
                'methods': ['GET'],
                'url': '/',
                'doc': "Documentation.",
                'changelog': {
                    4: 'changelog',
                },
                'request_schema': {'type': 'object'},
                'response_schema': {'type': 'object'},
                'introduced_at':  1,
            }},
            metadata,
        )

        self.assertEqual({
            'root': {
                'api': {'filename': fixture.path, 'lineno': 4},
                'changelog': {
                    4: {'filename': fixture.path, 'lineno': 7},
                },
                'request_schema': {
                    'filename': fixture.path,
                    'lineno': 5,
                },
                'response_schema': {
                    'filename': fixture.path,
                    'lineno': 6,
                },
                'view': {
                    'filename': fixture.path,
                    'lineno': 10,
                },
            }},
            locations,
        )

    def test_legacy_api_still_works(self):
        service = """

            from acceptable import *
            service = AcceptableService('service')

            root_api = service.api('/', 'root')
            root_api.changelog(4, "changelog")

            @root_api.view(introduced_at='1.0')
            @validate_body({'type': 'object'})
            @validate_output({'type': 'object'})
            def my_view():
                "Documentation."
        """
        fixture = self.useFixture(TemporaryModuleFixture('service', service))

        main.import_metadata(['service'])
        metadata, locations = main.parse(get_metadata())

        self.assertEqual({
            '$version': 4,
            'root': {
                'service': 'service',
                'api_group': None,
                'api_name': 'root',
                'methods': ['GET'],
                'url': '/',
                'doc': "Documentation.",
                'changelog': {
                    4: 'changelog',
                },
                'request_schema': {'type': 'object'},
                'response_schema': {'type': 'object'},
                'introduced_at':  1,
            }},
            metadata,
        )

        self.assertEqual({
            'root': {
                'api': {'filename': fixture.path, 'lineno': 4},
                'changelog': {
                    4: {'filename': fixture.path, 'lineno': 5},
                },
                'request_schema': {
                    'filename': fixture.path,
                    'lineno': 8,
                },
                'response_schema': {
                    'filename': fixture.path,
                    'lineno': 9,
                },
                'view': {
                    'filename': fixture.path,
                    'lineno': 10,
                },
            }},
            locations,
        )


def builder_installed():
    return subprocess.call(['which', 'documentation-builder']) == 0


class RenderMarkdownTests(testtools.TestCase):

    def metadata(self):
        metadata = OrderedDict()
        metadata['$version'] = 1
        metadata['api1'] = {
            'api_group': None,
            'api_name': 'api1',
            'methods': ['GET'],
            'url': '/',
            'doc': 'doc1',
            'changelog': {},
            'request_schema': {'request_schema': 1},
            'response_schema': {'response_schema': 2},
            'introduced_at':  1,
        }
        metadata['api2'] = {
            'api_group': None,
            'api_name': 'api1',
            'methods': ['GET'],
            'url': '/',
            'doc': 'doc2',
            'changelog': {},
            'request_schema': {'request_schema': 1},
            'response_schema': {'response_schema': 2},
            'introduced_at':  1,
        }
        return metadata

    def test_render_markdown_success(self):
        iterator = main.render_markdown(self.metadata(), 'SERVICE')
        output = OrderedDict((str(k), v) for k, v in iterator)

        self.assertEqual(set([
                'en/api1.md',
                'en/api2.md',
                'en/index.md',
                'en/metadata.yaml',
                'metadata.yaml',
            ]),
            set(output),
        )

        top_level_md = yaml.safe_load(output['metadata.yaml'])
        self.assertEqual(
            {'site_title': 'SERVICE Documentation: version 1'},
            top_level_md,
        )

        md = yaml.safe_load(output['en/metadata.yaml'])
        self.assertEqual({
                'navigation': [
                    {'location': 'index.md', 'title': 'Index'},
                    {'location': 'api1.md',  'title': 'api1'},
                    {'location': 'api2.md',  'title': 'api2'},
                ],
            },
            md
        )

    def test_render_markdown_undocumented(self):
        m = self.metadata()
        m['api2']['undocumented'] = True
        iterator = main.render_markdown(m, 'SERVICE')
        output = OrderedDict((str(k), v) for k, v in iterator)

        self.assertEqual(set([
                'en/api1.md',
                'en/index.md',
                'en/metadata.yaml',
                'metadata.yaml',
            ]),
            set(output),
        )

        md = yaml.safe_load(output['en/metadata.yaml'])
        self.assertEqual({
                'navigation': [
                    {'location': 'index.md', 'title': 'Index'},
                    {'location': 'api1.md',  'title': 'api1'},
                ],
            },
            md
        )

    def test_render_markdown_multiple_groups(self):
        metadata = self.metadata()
        metadata['api2']['api_group'] = 'group'
        iterator = main.render_markdown(metadata, 'SERVICE')
        output = OrderedDict((str(k), v) for k, v in iterator)

        self.assertEqual(set([
                'en/api1.md',
                'en/api2.md',
                'en/index.md',
                'en/metadata.yaml',
                'metadata.yaml',
            ]),
            set(output),
        )

        top_level_md = yaml.safe_load(output['metadata.yaml'])
        self.assertEqual(
            {'site_title': 'SERVICE Documentation: version 1'},
            top_level_md,
        )

        md = yaml.safe_load(output['en/metadata.yaml'])
        self.assertEqual({
                'navigation': [
                    {'location': 'index.md', 'title': 'Index'},
                    {'location': 'api1.md',  'title': 'api1'},
                    {'title': 'group', 'children': [
                        {'location': 'api2.md',  'title': 'api2'}
                    ]}
                ],
            },
            md
        )

    def test_render_markdown_group_omitted_with_undocumented(self):
        metadata = self.metadata()
        metadata['api2']['api_group'] = 'group'
        metadata['api2']['undocumented'] = True
        iterator = main.render_markdown(metadata, 'SERVICE')
        output = OrderedDict((str(k), v) for k, v in iterator)

        self.assertEqual(set([
                'en/api1.md',
                'en/index.md',
                'en/metadata.yaml',
                'metadata.yaml',
            ]),
            set(output),
        )

        top_level_md = yaml.safe_load(output['metadata.yaml'])
        self.assertEqual(
            {'site_title': 'SERVICE Documentation: version 1'},
            top_level_md,
        )

        md = yaml.safe_load(output['en/metadata.yaml'])
        self.assertEqual({
                'navigation': [
                    {'location': 'index.md', 'title': 'Index'},
                    {'location': 'api1.md',  'title': 'api1'},
                ],
            },
            md
        )

    @testtools.skipIf(
        not builder_installed(), 'documentation-builder not installed')
    @testtools.skipIf(PY2, 'PY3 only')
    def test_render_cmd_with_documentation_builder(self):
        # documentation-builder is a strict snap, can only work out of $HOME
        home = os.environ['HOME']
        markdown_dir = self.useFixture(fixtures.TempDir(rootdir=home))
        html_dir = self.useFixture(fixtures.TempDir(rootdir=home))

        with tempfile.NamedTemporaryFile('w') as metadata:
            metadata.write(json.dumps(self.metadata()))
            metadata.flush()

            args = main.parse_args([
                'render',
                metadata.name,
                '--name=SERVICE',
                '--dir={}'.format(markdown_dir.path),
            ])
            main.render_cmd(args)

        build = [
            'documentation-builder',
            '--base-directory={}'.format(markdown_dir.path),
            '--output-path={}'.format(html_dir.path),
        ]
        try:
            subprocess.check_output(build)
        except subprocess.CalledProcessError as e:
            print(e.output)
            raise

        p = partial(os.path.join, html_dir.path)
        self.assertTrue(os.path.exists(p('en/api1.html')))
        self.assertTrue(os.path.exists(p('en/api2.html')))
        self.assertTrue(os.path.exists(p('en/index.html')))


EXPECTED_LINT_OUTPUT = [
    'examples/api.py:22: Error: API foo at request_schema.required',
    'examples/api.py:22: Warning: API foo at request_schema.foo.doc',
    'examples/api.py:36: Warning: API foo at response_schema.foo_result.doc', # noqa
    'examples/api.py:36: Documentation: API foo at response_schema.foo_result.introduced_at'  # noqa
]


class LintTests(testtools.TestCase):

    def test_basic_api_changes(self):
        self.useFixture(CleanUpModuleImport('examples.api'))

        args = main.parse_args(
            ['lint', 'examples/api.json', 'examples.api'],
        )

        output = io.StringIO()
        result = main.lint_cmd(args, stream=output)
        self.assertEqual(1, result) == 1
        lines = output.getvalue().splitlines()

        for actual, expected in zip(lines, EXPECTED_LINT_OUTPUT):
            self.assertIn(expected, actual)


class VersionTests(testtools.TestCase):

    def test_version(self):
        self.useFixture(CleanUpModuleImport('examples.api'))

        args = main.parse_args(
            ['api-version', 'examples/api.json', 'examples.api'],
        )

        output = io.StringIO()
        result = main.version_cmd(args, stream=output)
        self.assertEqual(0, result) == 0
        self.assertEqual(
            'examples/api.json: 2\nexamples.api: 5\n',
            output.getvalue(),
        )
