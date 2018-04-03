import argparse
import json
from pathlib import Path
import sys

import yaml
from jinja2 import Environment, PackageLoader


env = Environment(
    loader=PackageLoader('acceptable', 'templates'),
    autoescape=False,
)


def main():
    cli_args = parse_args()
    path = Path(cli_args.dir)
    path.joinpath('en').mkdir(parents=True, exist_ok=True)
    render(cli_args.name, path, cli_args.metadata)


def parse_args(cli_args=sys.argv[1:]):
    parser = argparse.ArgumentParser(
        description='Render an acceptable generated metadata file to markdown '
                    'documentation'
    )
    parser.add_argument(
        'metadata',
        type=argparse.FileType('r'),
        default=sys.stdin,
    )
    parser.add_argument('--name', '-n', required=True, help='Name of service')
    parser.add_argument('--dir', '-d', default='docs', help='output directory')
    return parser.parse_args(cli_args)


def render(name, path, metadata_fp):
    metadata = json.load(metadata_fp)
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
