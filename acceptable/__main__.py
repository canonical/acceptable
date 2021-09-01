# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).
import argparse
from collections import defaultdict, OrderedDict
from importlib import import_module
import json
import os
import sys

from jinja2 import (
    ChoiceLoader,
    Environment,
    FileSystemLoader,
    PackageLoader,
)
import yaml

from acceptable import get_metadata, lint
from acceptable.dummy_importer import DummyImporterContext


def tojson_filter(json_object, indent=4):
    return json.dumps(json_object, indent=indent)


TEMPLATES = Environment(
    loader=ChoiceLoader([
        FileSystemLoader('./'),
        PackageLoader('acceptable', 'templates'),
    ]),
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
)
TEMPLATES.filters['tojson'] = tojson_filter


class ForceAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        if not namespace.update:
            if namespace.metadata:
                namespace.metadata.close()  # suppresses resource warning
            parser.error('--force can only be used with --update')
        else:
            namespace.force = True


def main():
    try:
        cli_args = parse_args()
        sys.exit(cli_args.func(cli_args))
    except Exception as e:
        raise
        sys.exit(str(e))


def parse_args(raw_args=None, parser_cls=None, stdin=None, stdout=None):
    if parser_cls is None:
        parser_cls = argparse.ArgumentParser
    if stdin is None:
        stdin = sys.stdin
    if stdout is None:
        stdout = sys.stdout

    parser = parser_cls(
        description='Tool for working with acceptable metadata',
    )
    subparser = parser.add_subparsers(dest='cmd')
    subparser.required = True

    metadata_parser = subparser.add_parser(
        'metadata', help='Import project and print extracted metadata in JSON')
    metadata_parser.add_argument('modules', nargs='+')
    metadata_parser.add_argument(
        '--dummy-dependencies', '-d',
        action='store_true',
        default=False,
        help='Import code in a sandbox where dependencies are mocked',
    )
    metadata_parser.add_argument(
        '--output',
        nargs='?',
        type=argparse.FileType('w'),
        default=stdout,
        help='metadata output file path, uses stdout if omitted'
    )
    metadata_parser.set_defaults(func=metadata_cmd)

    render_parser = subparser.add_parser(
        'render', help='Render markdown documentation for API metadata'
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
    render_parser.add_argument(
        '--page-template',
        type=TEMPLATES.get_template,
        default=TEMPLATES.get_template('api_group.md.j2'),
        help='Jinja2 template to render each API',
    )
    render_parser.add_argument(
        '--index-template',
        type=TEMPLATES.get_template,
        default=TEMPLATES.get_template('index.md.j2'),
        help='Jinja2 template to render the API index page',
    )
    render_parser.add_argument(
        '--extension', '-e',
        default='md',
        help='File extension for rendered documentation',
    )

    render_parser.set_defaults(func=render_cmd)

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

    doubles_parser = subparser.add_parser(
        'doubles',
        help='Generate test doubles'
    )
    doubles_parser.add_argument(
        'metadata',
        nargs='?',
        type=argparse.FileType('r'),
        default=stdin,
        help='metadata file path, uses stdin if omitted'
    )
    doubles_parser.add_argument(
        '-n', '--new-style',
        action='store_true',
        default=False,
        help='Generate new style ServiceFactory mocks',
    )
    doubles_parser.set_defaults(func=doubles_cmd)

    version_parser = subparser.add_parser(
        'api-version',
        help='Get the current API version from JSON meta, and '
             'optionally from current code also',
    )
    version_parser.add_argument(
        'metadata',
        nargs='?',
        type=argparse.FileType('r'),
        default=stdin,
        help='The JSON metadata for the API',
    )
    version_parser.add_argument(
        'modules',
        nargs='*',
        help='Optional modules to import for current imported API',
    )
    version_parser.set_defaults(func=version_cmd)

    return parser.parse_args(raw_args)


def metadata_cmd(cli_args):
    import_metadata(cli_args.modules, cli_args.dummy_dependencies)
    current, _ = get_metadata().serialize()
    cli_args.output.write(json.dumps(current, indent=2))


def add_working_dir_to_python_path():
    cwd = os.getcwd()
    if cwd not in sys.path:
        sys.path.insert(0, cwd)


def import_or_exec(path):
    """If path exists and ends in .py it is exec'd otherwise
    import is attempted"""
    if os.path.exists(path) and path.endswith('.py'):
        try:
            with open(path) as fd:
                exec(fd.read(), {}, {})
        except:
            raise Exception('Could not exec {!r}'.format(path))
    else:
        try:
            import_module(path)
        except:
            raise Exception(
                '{!r} did not look like a filepath and could not be '
                'loaded as a module'.format(path)
            )


def import_metadata_dummy_dependencies(module_paths):
    import acceptable._service
    add_working_dir_to_python_path()
    for path in module_paths:
        with DummyImporterContext(path):
            import_or_exec(path)


def import_metadata_real_dependencies(module_paths):
    add_working_dir_to_python_path()
    for path in module_paths:
        import_or_exec(path)


def import_metadata(module_paths, dummy_dependencies=False):
    """Imports modules or execs filepaths in order
    to get acceptable decorator metadata.
    """
    if dummy_dependencies:
        import_metadata_dummy_dependencies(module_paths)
    else:
        import_metadata_real_dependencies(module_paths)


def load_metadata(stream):
    """Load JSON metadata from opened stream."""
    try:
        metadata = json.load(
            stream, object_pairs_hook=OrderedDict)
    except json.JSONDecodeError as e:
        err = RuntimeError('Error parsing {}: {}'.format(stream.name, e))
        raise err from e
    else:
        # convert changelog keys back to ints for sorting
        for group in metadata:
            if group == '$version':
                continue
            apis = metadata[group]['apis']
            for api in apis.values():
                int_changelog = OrderedDict()
                for version, log in api.get('changelog', {}).items():
                    int_changelog[int(version)] = log
                api['changelog'] = int_changelog
    finally:
        stream.close()

    return metadata


def render_cmd(cli_args):
    root_dir = cli_args.dir
    en_dir = os.path.join(root_dir, 'en')
    if not os.path.exists(en_dir):
        os.makedirs(en_dir)
    metadata = load_metadata(cli_args.metadata)

    for path, content in render_markdown(metadata, cli_args):
        full_path = os.path.join(root_dir, path)
        with open(full_path, 'w', encoding='utf8') as f:
            f.write(content)


def render_markdown(metadata, cli_args):
    navigation = [{
        'title': 'Index',
        'location': 'index.' + cli_args.extension,
    }]
    version = metadata.pop('$version', None)
    changelog = defaultdict(dict)

    for group in metadata:
        apis = metadata[group]['apis']
        for api in apis.values():
            # collect global changelog
            for changed_version, log in api.get('changelog', {}).items():
                changelog[changed_version][(group, api['api_name'])] = log

        documented_apis = [
            api for api in apis.values()
            if not api.get('undocumented', False)
        ]

        if documented_apis:
            group_apis = []
            deprecated_apis = []
            for api in documented_apis:
                if api.get('deprecated_at', False):
                    deprecated_apis.append(api)
                else:
                    group_apis.append(api)
            sorted_apis = group_apis + deprecated_apis

            page_file = '{}.{}'.format(group, cli_args.extension)
            page = {'title': group.title(), 'location': page_file}
            navigation.append(page)

            path = os.path.join('en', page_file)
            yield path, cli_args.page_template.render(
                group_name=group,
                group_title=metadata[group].get('title', group),
                group_apis=sorted_apis,
                group_doc=metadata[group].get('docs', ''),
            )

    yield (
        os.path.join('en', 'index.' + cli_args.extension),
        cli_args.index_template.render(
            version=version,
            service_name=cli_args.name,
            changelog=changelog,
        )
    )

    # documentation-builder requires yaml metadata files in certain locations
    yield os.path.join('en', 'metadata.yaml'), yaml.safe_dump(
        {'navigation': navigation},
        default_flow_style=False,
        encoding=None,
    )
    site_meta = {
        'site_title': '{} Documentation: version {}'.format(
            cli_args.name,
            version,
        )
    }
    yield 'metadata.yaml', yaml.safe_dump(
        site_meta,
        default_flow_style=False,
        encoding=None,
    )


def lint_cmd(cli_args, stream=sys.stdout):
    metadata = load_metadata(cli_args.metadata)
    import_metadata(cli_args.modules)
    current, locations = get_metadata().serialize()

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
                json.dump(current, f, indent=2)

    return 1 if has_errors else 0


def doubles_cmd(cli_args, stream=sys.stdout):
    metadata = json.load(cli_args.metadata)
    if cli_args.new_style:
        from . import generate_mocks
        generate_mocks.generate_service_factory(
            metadata,
            stream=stream,
        )
    else:
        from . import generate_doubles
        generate_doubles.generate_service_mock_doubles(
            metadata,
            stream=stream
        )


def version_cmd(cli_args, stream=sys.stdout):
    metadata = load_metadata(cli_args.metadata)
    json_version = metadata['$version']
    import_version = None

    if cli_args.modules:
        import_metadata(cli_args.modules)
        import_version = get_metadata().current_version

    stream.write('{}: {}\n'.format(cli_args.metadata.name, json_version))

    if import_version is not None:
        if len(cli_args.modules) == 1:
            name = cli_args.modules[0]
        else:
            name = 'Imported API'
        stream.write('{}: {}\n'.format(name, import_version))

    return 0


if __name__ == '__main__':
    main()
