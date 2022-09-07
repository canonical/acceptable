"""
Helpers to translate acceptable metadata to OpenAPI specifications (OAS).
"""
from dataclasses import dataclass, field
from typing import Any

import yaml

from acceptable._service import APIMetadata


def _to_dict(source: Any):
    if hasattr(source, "_to_dict"):
        return source._to_dict()  # noqa
    elif type(source) == dict:
        source_dict = {}
        for key, value in source.items():
            source_dict[key] = _to_dict(value)
        return source_dict
    elif type(source) == list:
        source_list = []
        for item in source:
            source_list.append(_to_dict(item))
        return source_list
    elif hasattr(source, "__dict__"):
        source_dict = {}
        for key, value in source.__dict__.items():
            source_dict[key] = _to_dict(value)
        return source_dict
    else:
        return source


@dataclass
class OasInfo(object):
    description: str = ""
    version: str = ""
    title: str = ""
    tags: list = field(default_factory=lambda: [])
    contact: dict = field(default_factory=lambda: {"name": "", "email": ""})


@dataclass
class OasRoot31(object):
    openapi: str = "3.1.0"
    info: OasInfo = OasInfo()
    servers: dict = field(default_factory=lambda: {})
    paths: dict = field(default_factory=lambda: {})
    components_schemas: dict = field(default_factory=lambda: {})


def dump(metadata: APIMetadata, stream):
    service_name = None
    if len(metadata.services) == 1:
        service_name = list(metadata.services.keys())[0]

    oas = OasRoot31()
    oas.info.title = service_name or ""
    oas.info.version = metadata.current_version or ""

    oas_to_dict = _to_dict(oas)
    return yaml.safe_dump(oas_to_dict, stream, default_flow_style=False, encoding=None, )
