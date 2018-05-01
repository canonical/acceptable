# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).
import argparse
from collections import OrderedDict
from contextlib import contextmanager
from functools import partial
import io
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import yaml

import testtools
import fixtures

from acceptable import __main__ as main


# sys.exit on error, but rather throws an exception, so we can catch that in
# our tests:
class SaneArgumentParser(argparse.ArgumentParser):

    def error(self, message):
        raise RuntimeError(message)


class ParseArgsTests(testtools.TestCase):

    def test_error_with_no_args(self):
        self.assertRaisesRegex(
            RuntimeError,
            'the following arguments are required',
            main.parse_args,
            [],
            SaneArgumentParser,
        )

    def test_metadata_requires_files(self):
        self.assertRaisesRegex(
            RuntimeError,
            'the following arguments are required',
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
        self.assertTrue('hi', args.metadata.read())


@contextmanager
def temporary_module(name, code):
    old_sys_path = sys.path
    tempdir = tempfile.mkdtemp()
    path = os.path.join(tempdir, '{}.py'.format(name))
    with open(path, 'w') as f:
        f.write(textwrap.dedent(code))
    sys.path = [tempdir] + old_sys_path[:]
    yield
    sys.path = old_sys_path


class MetadataTests(testtools.TestCase):
    def test_legacy_api(self):
        service = """
            from acceptable import *
            service = AcceptableService('vendor')

            root_api = service.api('/', 'root')

            @root_api.view(introduced_at='1.0')
            @validate_body({'request_schema': 1})
            @validate_output({'response_schema': 2})
            def my_view():
                "Documentation."
        """

        with temporary_module('service', service):
            metadata = main.import_metadata(['service'])

        self.assertEqual({
            'root': {
                'api_name': 'root',
                'methods': ['GET'],
                'url': '/',
                'doc': "Documentation.",
                'request_schema': {'request_schema': 1},
                'response_schema': {'response_schema': 2},
                    'version':  1,
            }},
            metadata,
        )


def builder_installed():
    ps = subprocess.run(['which', 'documentation-builder'])
    return ps.returncode == 0


class RenderMarkdownTests(testtools.TestCase):

    @property
    def metadata(self):
        metadata = OrderedDict()
        metadata['api1'] = {
            'api_name': 'api1',
            'methods': ['GET'],
            'url': '/',
            'doc': 'doc1',
            'request_schema': {'request_schema': 1},
            'response_schema': {'response_schema': 2},
            'version':  1,
        }
        metadata['api2'] = {
            'api_name': 'api1',
            'methods': ['GET'],
            'url': '/',
            'doc': 'doc2',
            'request_schema': {'request_schema': 1},
            'response_schema': {'response_schema': 2},
            'version':  1,
        }
        return metadata

    def test_render_markdown_success(self):
        iterator = main.render_markdown(self.metadata, 'SERVICE')
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
        self.assertEqual({'site_title': 'SERVICE Documentation'}, top_level_md)

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

    @testtools.skipIf(
        not builder_installed(), 'documentation-builder not installed')
    def test_render_cmd_with_documentation_builder(self):
        # documentation-builder is a strict snap, can only work out of $HOME
        home = os.environ['HOME']
        markdown_dir = self.useFixture(fixtures.TempDir(rootdir=home))
        html_dir = self.useFixture(fixtures.TempDir(rootdir=home))

        with tempfile.NamedTemporaryFile('w') as metadata:
            metadata.write(json.dumps(self.metadata))
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
        ps = subprocess.run(
            build,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        self.assertEqual(ps.returncode, 0, ps.stdout)
        p = partial(os.path.join, html_dir.path)
        self.assertTrue(os.path.exists(p('en/api1.html')))
        self.assertTrue(os.path.exists(p('en/api2.html')))
        self.assertTrue(os.path.exists(p('en/index.html')))
