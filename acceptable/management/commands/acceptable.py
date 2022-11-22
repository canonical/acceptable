# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).
"""acceptable - Programatic API Metadata for Flask apps."""

import argparse
import json
import sys

from django.core.management.base import BaseCommand

from acceptable import get_metadata, openapi
from acceptable.__main__ import load_metadata
from acceptable.djangoutil import get_urlmap


class Command(BaseCommand):
    help = "Generate Acceptable API Metadata from project"

    def add_arguments(self, parser):
        # Handle our subparsers in a way that is supported in Django 2.1+
        subparsers = parser.add_subparsers(dest="cmd")

        metadata_parser = subparsers.add_parser(
            "metadata", help="Import project and print extracted metadata in json"
        )
        metadata_parser.set_defaults(func=self.metadata)

        openapi_parser = subparsers.add_parser(
            "openapi", help="Import project and print as OpenAPI 3.1 schema"
        )
        openapi_parser.set_defaults(func=self.openapi)

        version_parser = subparsers.add_parser(
            "api-version",
            help="Get the current api version from json meta, and "
            "optionally from current code also",
        )
        version_parser.add_argument(
            "metadata",
            nargs="?",
            type=argparse.FileType("r"),
            default=sys.stdin,
            help="The json metadata for the api",
        )
        version_parser.set_defaults(func=self.version)

    def handle(self, *args, **options):
        get_urlmap()  # this imports all urls and initialises the url mappings
        func = options["func"]
        func(options, get_metadata())

    def metadata(self, _, metadata):
        _serial, _ = metadata.serialize()
        print(json.dumps(_serial, indent=2))

    def openapi(self, _, metadata):
        print(openapi.dump(metadata))

    def version(self, options, metadata, stream=sys.stdout):
        file_metadata = load_metadata(options["metadata"])
        json_version = file_metadata["$version"]
        serialized, _ = metadata.serialize()
        import_version = serialized["$version"]
        stream.write("{}: {}\n".format(options["metadata"].name, json_version))
        stream.write("Imported API: {}\n".format(import_version))
