# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).

import argparse
from importlib import import_module
import json
import os
from pathlib import Path
import sys

from jinja2 import Environment, PackageLoader
import yaml

from acceptable._service import Metadata
from acceptable import lint


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
        'metadata', help='Import project and print extracted metadata in json')
    metadata_parser.add_argument('modules', nargs='+')
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

    class ForceAction(argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):
            if not namespace.update:
                parser.error('--force can only be used with --update')
            else:
                namespace.force = True

    lint_parser = subparser.add_parser(
        'lint', help='Compare current metadata against file metadata')
    lint_parser.add_argument(
        'metadata',
        nargs='?',
        type=argparse.FileType('r'),
    )
    lint_parser.add_argument('modules', nargs='+')
    lint_parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        default=False,
        help='Do not emit warnings',
    )
    lint_parser.add_argument(
        '--strict', '--pedantic', '--overhead',
        action='store_true',
        default=False,
        help='Even warnings count as failure',
    )
    lint_parser.add_argument(
        '--update',
        action='store_true',
        default=False,
        help='Update metadata file to new metadata if lint passes',
    )
    lint_parser.add_argument(
        '--force',
        action=ForceAction,
        nargs=0,
        default=False,
        help='Update metadata even if linting fails',
    )

    lint_parser.set_defaults(func=lint_cmd)

    return parser.parse_args(raw_args)


def metadata_cmd(cli_args):
    sys.path.insert(0, os.getcwd())
    metadata, _ = import_metadata(cli_args.modules)
    print(json.dumps(metadata, indent=2, sort_keys=True))


def import_metadata(module_paths):
    """Import all the given modules, and then extract the parsed metadata."""
    for path in module_paths:
        import_module(path)

    api_metadata = {}
    locations = {}
    for (svc_name, group), apis in Metadata.services.items():
        for name, api in apis.items():
            api_metadata[name] = {
                'api_name': api.name,
                'introduced_at': api.introduced_at,
                'methods': api.methods,
                'url': api.url,
                'request_schema': api.request_schema,
                'response_schema': api.response_schema,
                'doc': api.docs,
                'changelog': api._changelog,
            }

            locations[name] = {
                'api': api.location,
                'request_schema': api._request_schema_location,
                'response_schema': api._response_schema_location,
                'changelog': api._changelog_locations,
                'view': api.view_fn_location,
            }

    return api_metadata, locations


def render_cmd(cli_args):
    root_dir = Path(cli_args.dir)
    root_dir.joinpath('en').mkdir(parents=True, exist_ok=True)
    try:
        metadata = json.load(cli_args.metadata)
    except json.JSONDecodeError as e:
        return 'Error parsing {}: {}'.format(cli_args.metadata.name, e)
    finally:
        cli_args.metadata.close()

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


def lint_cmd(cli_args, stream=sys.stdout):
    sys.path.insert(0, os.getcwd())
    current, locations = import_metadata(cli_args.modules)
    try:
        metadata = json.load(cli_args.metadata)
    except json.JSONDecodeError as e:
        return 'Error parsing {}: {}'.format(cli_args.metadata.name, e)
    finally:
        cli_args.metadata.close()

    has_errors = False
    display_level = lint.WARNING
    error_level = lint.DOCUMENTATION

    if cli_args.strict:
        display_level = lint.WARNING
        error_level = lint.WARNING
    elif cli_args.quiet:
        display_level = lint.DOCUMENTATION

    for message in lint.metadata_lint(metadata, current, locations):
        if message.level >= display_level:
            stream.write('{}\n'.format(message))

        if message.level >= error_level:
            has_errors = True

    if cli_args.update:
        if not has_errors or cli_args.force:
            with open(cli_args.metadata.name, 'w') as f:
                json.dump(current, f, indent=2, sort_keys=True)

    return 1 if has_errors else 0


if __name__ == '__main__':
    main()
