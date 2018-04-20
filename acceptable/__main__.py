# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).

import argparse
import json
from pathlib import Path
import sys

from jinja2 import Environment, PackageLoader
import yaml

from acceptable._build_doubles import extract_schemas_from_file


def main():
    cli_args = parse_args()
    sys.exit(cli_args.func(cli_args))


def parse_args(raw_args=None, parser_cls=None, stdin=None):
    if parser_cls is None:
        parser_cls = argparse.ArgumentParser
    if stdin is None:
        stdin = sys.stdin

    parser = parser_cls(
        description='Tool for working with acceptable metadata',
    )
    subparser = parser.add_subparsers(dest='cmd')
    subparser.required = True

    metadata_parser = subparser.add_parser(
        'metadata', help='Scan files and print extracted metadata in json')
    metadata_parser.add_argument('files', nargs='+')
    metadata_parser.set_defaults(func=metadata_cmd)

    render_parser = subparser.add_parser(
        'render', help='Render markdown documentation for api metadata'
    )
    render_parser.add_argument(
        'metadata',
        nargs='?',
        type=argparse.FileType('r'),
        default=stdin,
    )
    render_parser.add_argument(
        '--name', '-n', required=True, help='Name of service')
    render_parser.add_argument(
        '--dir', '-d', default='docs', help='output directory')
    render_parser.set_defaults(func=render_cmd)

    return parser.parse_args(raw_args)


def metadata_cmd(cli_args):
    metadata = scan_metadata(cli_args.files)
    print(json.dumps(metadata, indent=2, sort_keys=True))
    return 0


def scan_metadata(files):
    # This uses AST parsing for now. In future, we might just import code.
    schemas = []
    metadata = {}
    for path in files:
        schemas.extend(extract_schemas_from_file(path))
    for schema in schemas:
        metadata[schema.view_name] = {
            'api_name': schema.view_name,
            'version': int(float(schema.version)),  # convert any '1.0' strings
            'methods': schema.methods,
            'url': schema.url,
            'request_schema': schema.input_schema,
            'response_schema': schema.output_schema,
            'doc': schema.doc,
        }
    return metadata


def render_cmd(cli_args):
    root_dir = Path(cli_args.dir)
    root_dir.joinpath('en').mkdir(parents=True, exist_ok=True)
    try:
        metadata = json.load(cli_args.metadata)
    except json.JSONDecodeError as e:
        return 'Error parsing {}: {}'.format(cli_args.metadata.name, e)
    cli_args.metadata.close()  # suppresses ResourceWarning

    for path, content in render_markdown(metadata, cli_args.name):
        root_dir.joinpath(path).write_text(content)


def render_markdown(metadata, name):
    env = Environment(
        loader=PackageLoader('acceptable', 'templates'),
        autoescape=False,
    )
    docs_metadata = {
        'navigation': [{'title': 'Index', 'location': 'index.md'}]
    }
    pages = []
    en = Path('en')
    page = env.get_template('api_page.md.j2')
    index = env.get_template('index.md.j2')

    for api_name, api in metadata.items():
        page_file = '{}.md'.format(api_name)
        pages.append({'title': api_name, 'location': page_file})
        yield en / page_file, page.render(name=api_name, **api)

    docs_metadata['navigation'].extend(
        sorted(pages, key=lambda k: k['title']))

    yield en / 'index.md', index.render(service_name=name)

    # documentation-builder requires yaml metadata files in certain locations
    yield en / 'metadata.yaml', yaml.safe_dump(docs_metadata)
    yield Path('metadata.yaml'), yaml.safe_dump(
        {'site_title': name + ' Documentation'}
    )


if __name__ == '__main__':
    main()
