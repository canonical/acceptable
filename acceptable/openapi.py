"""
Helpers to translate acceptable metadata to OpenAPI specifications (OAS).
"""
import logging
from dataclasses import dataclass, field
from typing import Any

import yaml

from acceptable._service import APIMetadata, AcceptableAPI


def _to_dict(source: Any):
    if hasattr(source, "_to_dict"):
        return source._to_dict()  # noqa
    elif type(source) == dict:
        return {key: _to_dict(value) for key, value in source.items()}
    elif type(source) == list:
        return [_to_dict(value) for value in source]
    elif hasattr(source, "__dict__"):
        return {key: _to_dict(value) for key, value in source.__dict__.items()}
    else:
        return source


def tidy_string(untidy: str):
    tidy = str(untidy).replace("\n", " ")
    while "  " in tidy:
        tidy = tidy.replace("  ", " ")
    return tidy.strip()


def get_head_of_single_item_list(item_list, item_name):
    count = len(item_list)
    if count == 1:
        return item_list[0]
    else:
        logging.warning(
            f"Encountered {item_name} list with {count} items. Treating as empty."
        )
        return None


def convert_endpoint_to_operation(endpoint: AcceptableAPI):
    return OasOperation(
        tags=[endpoint.service.group] if endpoint.service.group else ["none"],
        summary=endpoint.title,
        description=tidy_string(endpoint.docs),
        operation_id=endpoint.name,
    )


@dataclass
class OasOperation:
    tags: list
    summary: str
    description: str
    operation_id: str

    def _to_dict(self):
        result = {
            "tags": self.tags,
            "summary": self.summary,
            "description": tidy_string(self.description) or "None.",
            "operationId": self.operation_id,
            "requestBody": {
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/Default"}
                    }
                }
            },
            "responses": {
                "200": {
                    "description": "OK",
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/Default",
                            }
                        }
                    },
                },
            },
        }

        if self.summary is None or self.summary == "":
            result.pop("summary")

        return result


@dataclass
class OasPath:
    operation: dict = field(default_factory=lambda: {})

    def _to_dict(self):
        return _to_dict(self.operation)


@dataclass
class OasInfo:
    description: str = ""
    version: str = ""
    title: str = ""
    contact: dict = field(
        default_factory=lambda: {"name": "", "email": "example@example.example"}
    )


@dataclass
class OasRoot31:
    openapi: str = "3.1.0"
    info: OasInfo = OasInfo()
    tags: list = field(default_factory=lambda: [])
    servers: list = field(default_factory=lambda: [{"url": "http://localhost"}])
    paths: dict = field(default_factory=lambda: {})

    def _to_dict(self):
        return {
            "openapi": self.openapi,
            "info": _to_dict(self.info),
            "servers": _to_dict(self.servers),
            "tags": _to_dict(self.tags),
            "paths": _to_dict(self.paths),
            "components": {
                "schemas": {
                    "Default": {
                        "type": "object",
                        "properties": {
                            "code": {
                                "type": "integer",
                                "format": "int32",
                            }
                        },
                    }
                }
            },
        }


def dump(metadata: APIMetadata, stream=None):
    oas = OasRoot31()
    oas.info.title = (
        get_head_of_single_item_list(list(metadata.services.keys()), "service")
        or "None."
    )
    oas.info.description = oas.info.title
    oas.info.version = "2.0." + str(metadata.current_version)
    tags = set()

    for _, service_group in metadata.services.items():
        for _, api_group in service_group.items():
            for _, endpoint in api_group.items():
                method = get_head_of_single_item_list(endpoint.methods, "method")
                if method is not None:
                    method = str.lower(method)
                    url = endpoint.url  # TODO: tidy and extract parameters
                    operation = convert_endpoint_to_operation(endpoint)
                    tags.update(set(operation.tags))
                    path = OasPath()
                    path.operation[method] = operation
                    oas.paths[url] = path

    for tag in tags:
        oas.tags.append({"name": tag})

    return yaml.safe_dump(
        _to_dict(oas), stream, default_flow_style=False, encoding=None
    )
