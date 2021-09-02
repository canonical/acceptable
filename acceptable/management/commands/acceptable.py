
# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).
"""acceptable - Programatic API Metadata for Flask apps."""

import argparse
import json
import sys

from django.core.management.base import BaseCommand, CommandParser

from acceptable import get_metadata
from acceptable.djangoutil import get_urlmap
from acceptable.__main__ import load_metadata


class Command(BaseCommand):
    help = 'Generate Acceptable API Metadata from project'

    def add_arguments(self, parser):
        # Handle our subparsers in a way that is suppoert in Django 2.1+
        subparsers = parser.add_subparsers(dest='cmd')

        metadata_parser = subparsers.add_parser(
            'metadata',
            help='Import project and print extracted metadata in json')
        metadata_parser.set_defaults(func=self.metadata)

        version_parser = subparsers.add_parser(
            'api-version',
            help='Get the current api version from json meta, and '
                 'optionally from current code also',
        )
        version_parser.add_argument(
            'metadata',
            nargs='?',
            type=argparse.FileType('r'),
            default=sys.stdin,
            help='The json metadata for the api',
        )
        version_parser.set_defaults(func=self.version)

    def handle(self, *args, **options):
        get_urlmap()  # this imports all urls and initialises the url mappings
        func = options['func']
        current, _ = get_metadata().serialize()
        func(options, current)

    def metadata(self, options, current):
        print(json.dumps(current, indent=2))

    def version(self, options, current, stream=sys.stdout):
        file_metadata = load_metadata(options['metadata'])
        json_version = file_metadata['$version']
        import_version = current['$version']
        stream.write('{}: {}\n'.format(options['metadata'].name, json_version))
        stream.write('Imported API: {}\n'.format(import_version))
