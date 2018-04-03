import argparse
import json
from pathlib import Path
import sys

import yaml
from jinja2 import Environment, PackageLoader

from acceptable._build_doubles import extract_schemas_from_file

env = Environment(
    loader=PackageLoader('acceptable', 'templates'),
    autoescape=False,
)


def main():
    cli_args = parse_args()
    sys.exit(cli_args.func(cli_args))


def parse_args(cli_args=sys.argv[1:]):
    parser = argparse.ArgumentParser(
        description='Tool for working with acceptable metadata',
    )
    subparser = parser.add_subparsers(dest='cmd')
    subparser.required = True

    metadata_parser = subparser.add_parser(
        'metadata', help='Scan files and print extracted metadata in json')
    metadata_parser.add_argument('files', nargs='+')
    metadata_parser.set_defaults(func=scan_metadata)

    render_parser = subparser.add_parser(
        'render', help='Render markdown documentation for api metadata'
    )
    render_parser.add_argument(
        'metadata',
        nargs='?',
        type=argparse.FileType('r'),
        default=sys.stdin,
    )
    render_parser.add_argument(
        '--name', '-n', required=True, help='Name of service')
    render_parser.add_argument(
        '--dir', '-d', default='docs', help='output directory')
    render_parser.set_defaults(func=render_markdown)

    return parser.parse_args(cli_args)


def scan_metadata(cli_args):
    # This uses AST parsing for now. In future, we might just import code.
    schemas = []
    metadata = {}
    for path in cli_args.files:
        schemas.extend(extract_schemas_from_file(path))
    for schema in schemas:
        metadata[schema.view_name] = {
            'view_name': schema.view_name,
            'version': int(float(schema.version)),  # convert any '1.0' strings
            'methods': schema.methods,
            'url': schema.url,
            'request_schema': schema.input_schema,
            'response_schema': schema.output_schema,
            'doc': schema.doc,
            'function_name': schema.function_name,
        }
    print(json.dumps(metadata, indent=2, sort_keys=True))
    return 0


def render_markdown(cli_args):
    path = Path(cli_args.dir)
    path.joinpath('en').mkdir(parents=True, exist_ok=True)
    name = cli_args.name
    metadata = json.load(cli_args.metadata)
    docs_metadata = {
        'navigation': [{'title': 'Index', 'location': 'index.md'}]
    }
    pages = []
    page = env.get_template('api_page.md.j2')
    en = path / 'en'
    index = env.get_template('index.md.j2')

    for api_name, api in metadata.items():
        page_file = '{}.md'.format(api_name)
        pages.append({'title': api_name, 'location': page_file})
        en.joinpath(page_file).write_text(page.render(name=api_name, **api))

    docs_metadata['navigation'].extend(
        sorted(pages, key=lambda k: k['title']))

    en.joinpath('index.md').write_text(index.render(service_name=name))
    en.joinpath('metadata.yaml').write_text(yaml.safe_dump(docs_metadata))
    path.joinpath('metadata.yaml').write_text(
        yaml.safe_dump({'site_title': name + ' Documentation'})
    )
    return 0


if __name__ == '__main__':
    main()
