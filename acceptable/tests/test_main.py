# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).
import argparse
from collections import OrderedDict
import io
import tempfile
import textwrap

from testtools import TestCase

from acceptable import __main__ as main


# sys.exit on error, but rather throws an exception, so we can catch that in
# our tests:
class SaneArgumentParser(argparse.ArgumentParser):

    def error(self, message):
        raise RuntimeError(message)


class ParseArgsTests(TestCase):

    def test_error_with_no_args(self):
        self.assertRaises(
            RuntimeError,
            main.parse_args,
            [],
            SaneArgumentParser,
        )

    def test_metadata_requires_files(self):
        self.assertRaises(
            RuntimeError,
            main.parse_args,
            ['metadata'],
            SaneArgumentParser,
        )

    def test_metadata_parses_files(self):
        args = main.parse_args(['metadata', 'foo', 'bar'])
        self.assertEqual(['foo', 'bar'], args.files)
        self.assertEqual(main.metadata_cmd, args.func)

    def test_render_parses_file(self):
        with tempfile.NamedTemporaryFile('w') as api:
            api.write('hi')
            api.flush()
            args = main.parse_args(['render', '--name=name', api.name])

        self.assertTrue('hi', args.metadata.read())
        self.assertEqual(main.render_cmd, args.func)

    def test_render_parses_stdin_with_no_metadata(self):
        stdin = io.StringIO('hi')
        args = main.parse_args(['render', '--name=name'], stdin=stdin)
        self.assertTrue('hi', args.metadata.read())


class ScanMetadata(TestCase):

    def write_file(self, code):
        f = tempfile.NamedTemporaryFile('w')
        f.write(textwrap.dedent(code))
        f.flush()
        return f

    def test_single_file(self):
        code = self.write_file("""
            service = AcceptableService('vendor')

            root_api = service.api('/', 'root')

            @root_api.view(introduced_at='1.0')
            @validate_body({'request_schema': 1})
            @validate_output({'response_schema': 2})
            def my_view():
                "documentation"
            """)

        metadata = main.scan_metadata([code.name])
        self.assertEqual({
            'root': {
                'doc': "documentation",
                'methods': ['GET'],
                'request_schema': {'request_schema': 1},
                'response_schema': {'response_schema': 2},
                'url': '/',
                'version':  1,
                'api_name': 'root',
            }},
            metadata,
        )


class RenderMarkdown(TestCase):

    def test_render_markdown(self):
        metadata = OrderedDict()
        metadata['api1'] = {
            'doc': 'doc1',
            'methods': ['GET'],
            'request_schema': {'request_schema': 1},
            'response_schema': {'response_schema': 2},
            'url': '/',
            'version':  1,
            'api_name': 'api1',
        }
        metadata['api2'] = {
            'doc': 'doc2',
            'methods': ['GET'],
            'request_schema': {'request_schema': 1},
            'response_schema': {'response_schema': 2},
            'url': '/',
            'version':  1,
            'api_name': 'api1',
        }

        markdown = OrderedDict((str(k), v) for k, v in
                               main.render_markdown(metadata, 'SERVICE'))

        self.assertEqual([
                'en/api1.md',
                'en/api2.md',
                'en/index.md',
                'en/metadata.yaml',
                'metadata.yaml',
            ],
            list(markdown),
        )
