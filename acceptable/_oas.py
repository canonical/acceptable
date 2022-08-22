"""
Helpers to translate acceptable metadata to OpenAPI specifications (OAS).
"""

import sys
from typing import Any

import yaml


def to_dict(source: Any):

    if hasattr(source, "to_dict"):
        return source.to_dict()
    elif type(source) == dict:
        source_dict = {}
        for key, value in source.items():
            source_dict[key] = to_dict(value)
        return source_dict
    elif type(source) == list:
        source_list = []
        for item in source:
            source_list.append(to_dict(item))
        return source_list
    else:
        return source


def dump_oas(schema, stream):

    return yaml.safe_dump(
        to_dict(schema),
        stream,
        default_flow_style=False,
        encoding=None,
    )


def print_oas(schema):
    dump_oas(schema, sys.stdout)


def store_oas(schema, path):
    with open(path, "w") as w:
        dump_oas(schema, w)
