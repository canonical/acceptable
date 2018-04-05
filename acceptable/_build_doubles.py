# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).

"""Build Service Doubles:

This module contains the entry point used to extract schemas from python source
files. The `main` function is installed as a console_script, and has several
modes of operation:

 - The 'scan_file' command allows a user to scan a random python source file
   and inspect what service doubles would be extracted from it. This is useful
   for ensuring that service_doubles can be extracted from a python source file
   before committing it.

 - The 'build' command takes a config file containing service names and
   locations, and builds a set of service_doubles based on that config.

In both cases, the service doubles are built by doing an AST parse of the
python source file in question and extracting calls to acceptable functions.
"""

import argparse
import ast
import collections
import json
import logging
import os.path
import subprocess
import sys
import tempfile
import textwrap


def main():
    args = parse_args()
    args.func(args)


def parse_args(arg_list=None, parser_class=None):
    parser = parser_class() if parser_class else argparse.ArgumentParser()
    subparser = parser.add_subparsers(dest='cmd')
    subparser.required = True
    scan_file_parser = subparser.add_parser(
        'scan-file', help='Scan a file, print extracted service doubles.')
    scan_file_parser.add_argument('file', type=str)
    scan_file_parser.set_defaults(func=scan_file)

    build_parser = subparser.add_parser(
        'build', help='build service doubles.')
    build_parser.add_argument('config_file', type=str)
    build_parser.set_defaults(func=build_service_doubles)

    return parser.parse_args(arg_list)


def scan_file(args):
    service_schemas = extract_schemas_from_file(args.file)
    print(render_service_double(
        'UNKNOWN', service_schemas, 'scan-file %s' % args.file))


def build_service_doubles(args):
    with tempfile.TemporaryDirectory() as workdir:
        service_config = read_service_config_file(args.config_file)
        target_root = os.path.dirname(args.config_file)
        for service_name in service_config['services']:
            service = service_config['services'][service_name]
            source_url = service['git_source']
            branch = service.get('git_branch')
            service_dir = fetch_service_source(
                workdir, service_name, source_url, branch)
            service_schemas = []
            for scan_path in service['scan_paths']:
                abs_path = os.path.join(service_dir, scan_path)
                service_schemas.extend(extract_schemas_from_file(abs_path))
            rendered = render_service_double(
                service_name, service_schemas, 'build %s' % args.config_file)
            write_service_double_file(target_root, service_name, rendered)
            print("Rendered schemas file for %s service: %d schemas" % (
                service, len(service_schemas)))


def read_service_config_file(config_path):
    with open(config_path, 'r') as config_file:
        return json.load(config_file)


def fetch_service_source(workdir, service_name, source_url, branch=None):
    print("Cloning source for %s service." % service_name)
    target_dir = os.path.join(workdir, service_name)
    cmd = ['git', 'clone']
    if branch is not None:
        cmd.extend(['-b', branch])
    cmd.extend([source_url, target_dir])
    subprocess.check_call(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    return target_dir


# ViewSchema contains all the information for a flask view...
ViewSchema = collections.namedtuple(
    'ViewSchema',
    [
        'view_name',      # The name of the view function.
        'version',        # The version the view was introduced at.
        'input_schema',   # The schema for requests to the service.
        'output_schema',  # The schema for responses from the service
        'methods',        # The methods this view supports.
        'url',            # The URL this view is mounted at.
        'doc',            # The documentation for this url
    ]
)


def extract_schemas_from_file(source_path):
    """Extract schemas from 'source_path'.

    :returns: a list of ViewSchema objects on success, None if no schemas
        could be extracted.
    """
    logging.info("Extracting schemas from %s", source_path)
    try:
        with open(source_path, 'r') as source_file:
            source = source_file.read()
    except (FileNotFoundError, PermissionError) as e:
        logging.error("Cannot extract schemas: %s", e.strerror)
    else:
        try:
            schemas = extract_schemas_from_source(source, source_path)
        except SyntaxError as e:
            logging.error("Cannot extract schemas: %s", str(e))
        else:
            logging.info(
                "Extracted %d %s",
                len(schemas),
                "schema" if len(schemas) == 1 else "schemas")
            return schemas


def extract_schemas_from_source(source, filename='<unknown>'):
    """Extract schemas from 'source'.

    The 'source' parameter must be a string, and should be valid python
    source.

    If 'source' is not valid python source, a SyntaxError will be raised.

    :returns: a list of ViewSchema objects.
    """
    # Track which acceptable services have been configured.
    acceptable_services = set()
    # Track which acceptable views have been configured:
    acceptable_views = {}
    schemas_found = []
    ast_tree = ast.parse(source, filename)

    assigns = [n for n in ast_tree.body if isinstance(n, ast.Assign)]
    call_assigns = [n for n in assigns if isinstance(n.value, ast.Call)]

    # We need to extract the AcceptableService-related views. We parse the
    # assignations twice: The first time to extract the AcceptableService
    # instances, the second to extract the views created on those services.
    for assign in call_assigns:
        if isinstance(assign.value.func, ast.Attribute):
            continue
        if assign.value.func.id == 'AcceptableService':
            for target in assign.targets:
                acceptable_services.add(target.id)

    for assign in call_assigns:
        # only consider calls which are attribute accesses, AND
        # calls where the object being accessed is in acceptable_services, AND
        # calls where the attribute being accessed is the 'api' method.
        if isinstance(assign.value.func, ast.Attribute) and \
           assign.value.func.value.id in acceptable_services and \
           assign.value.func.attr == 'api':
            # this is a view. We need to extract the url and methods specified.
            # they may be specified positionally or via a keyword.
            url = None
            name = None
            # methods has a default value:
            methods = ['GET']

            # This is a view - the URL is the first positional argument:
            args = assign.value.args
            if len(args) >= 1:
                url = ast.literal_eval(args[0])
            if len(args) >= 2:
                name = ast.literal_eval(args[1])
            kwargs = assign.value.keywords
            for kwarg in kwargs:
                if kwarg.arg == 'url':
                    url = ast.literal_eval(kwarg.value)
                if kwarg.arg == 'methods':
                    methods = ast.literal_eval(kwarg.value)
                if kwarg.arg == 'view_name':
                    name = ast.literal_eval(kwarg.value)
            if url and name:
                for target in assign.targets:
                    acceptable_views[target.id] = {
                        'url': url,
                        'name': name,
                        'methods': methods,
                    }

    # iterate over all functions, attempting to find the views.
    functions = [n for n in ast_tree.body if isinstance(n, ast.FunctionDef)]
    for function in functions:
        input_schema = None
        output_schema = None
        doc = ast.get_docstring(function)
        api_options_list = []
        for decorator in function.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            if isinstance(decorator.func, ast.Attribute):
                decorator_name = decorator.func.value.id
                # extract version this view was introduced at, which can be
                # specified as an arg or a kwarg:
                version = None
                for kwarg in decorator.keywords:
                    if kwarg.arg == 'introduced_at':
                        version = ast.literal_eval(kwarg.value)
                        break
                if len(decorator.args) == 1:
                    version = ast.literal_eval(decorator.args[0])

                if decorator_name in acceptable_views:
                    api_options = acceptable_views[decorator_name]
                    api_options['version'] = version
                    api_options_list.append(api_options)
            else:
                decorator_name = decorator.func.id
                if decorator_name == 'validate_body':
                    # TODO: Check that nothing in the tree below
                    # decorator.args[0] is an instance of 'ast.Name', and
                    # print a nice error message if it is.
                    input_schema = ast.literal_eval(decorator.args[0])
                if decorator_name == 'validate_output':
                    output_schema = ast.literal_eval(decorator.args[0])
        for api_options in api_options_list:
            schema = ViewSchema(
                    view_name=api_options['name'],
                    version=api_options['version'],
                    input_schema=input_schema,
                    output_schema=output_schema,
                    methods=api_options['methods'],
                    url=api_options['url'],
                    doc=doc,
                )
            schemas_found.append(schema)
    return schemas_found


def render_value(value):
    """Render a value, ensuring that any nested dicts are sorted by key."""
    if isinstance(value, list):
        return '[' + ', '.join(render_value(v) for v in value) + ']'
    elif isinstance(value, dict):
        return (
            '{' +
            ', '.join('{k!r}: {v}'.format(
                k=k, v=render_value(v)) for k, v in sorted(value.items())) +
            '}')
    else:
        return repr(value)


def render_service_double(service_name, schemas, regenerate_args):
    header = textwrap.dedent("""\
        # This file is AUTO GENERATED. Do not edit this file directly. Instead,
        # re-generate it by running '{progname} {regenerate_args}'.

        from acceptable._doubles import service_mock
        """.format(
            progname=os.path.basename(sys.argv[0]),
            regenerate_args=regenerate_args,
        ))

    rendered_schemas = []
    for schema in schemas:
        double_name = '%s_%s' % (
            schema.view_name, schema.version.replace('.', '_'))
        rendered_schema = textwrap.dedent("""\
        {double_name} = service_mock(
            service={service_name!r},
            methods={schema.methods!r},
            url={schema.url!r},
            input_schema={input_schema},
            output_schema={output_schema},
        )
        """).format(
            double_name=double_name,
            schema=schema,
            service_name=service_name,
            input_schema=render_value(schema.input_schema),
            output_schema=render_value(schema.output_schema),
        )

        rendered_schemas.append(rendered_schema)

    rendered_file = '{header}\n\n{schemas}\n'.format(
        header=header,
        schemas='\n\n'.join(rendered_schemas)
    )
    return rendered_file


def write_service_double_file(target_root, service_name, rendered):
    """Render syntactically valid python service double code."""
    target_path = os.path.join(
        target_root,
        'snapstore_schemas', 'service_doubles', '%s.py' % service_name
    )
    with open(target_path, 'w') as target_file:
        target_file.write(rendered)
