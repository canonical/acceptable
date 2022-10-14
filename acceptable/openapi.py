"""
Helpers to translate acceptable metadata to OpenAPI specifications (OAS).
"""
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Tuple

import yaml

from acceptable._service import APIMetadata, AcceptableAPI


@dataclass
class OasOperation:
    tags: list
    summary: str
    description: str
    operation_id: str
    request_schema: Any
    response_schema: Any
    path_parameters: dict

    def _parameters_to_openapi(self):
        # To ensure a stable output we sort the parameter dictionary.

        for key, value in sorted(self.path_parameters.items()):
            yield {
                "name": key,
                "in": "path",
                "required": True,
                "schema": {"type": value},
            }

    def _to_dict(self):
        result = {
            "tags": self.tags,
            "summary": self.summary,
            "description": tidy_string(self.description) or "None.",
            "operationId": self.operation_id,
            "parameters": list(self._parameters_to_openapi()),
            "requestBody": {
                "content": {
                    "application/json": {"schema": {"$ref": self.request_schema}}
                }
            },
            "responses": {
                "200": {
                    "description": self.summary or "OK",
                    "content": {
                        "application/json": {"schema": {"$ref": self.response_schema}}
                    },
                }
            },
        }

        # drop empty summary
        if not self.summary:
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
                        "properties": {"code": {"type": "integer", "format": "int32"}},
                    }
                }
            },
        }


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


def tidy_string(untidy: Any):
    tidy = str(untidy).replace("\n", " ")
    while "  " in tidy:
        tidy = tidy.replace("  ", " ")
    return tidy.strip()


def convert_endpoint_to_operation(endpoint: AcceptableAPI, path_parameters: dict):

    if endpoint.request_schema is None:
        _request_schema = "#/components/schemas/Default"
    else:
        _request_schema = json.loads(json.dumps(endpoint.request_schema))

    if endpoint.response_schema is None:
        _response_schema = "#/components/schemas/Default"
    else:
        _response_schema = json.loads(json.dumps(endpoint.response_schema))

    return OasOperation(
        tags=[endpoint.service.group] if endpoint.service.group else ["none"],
        summary=endpoint.title,
        description=tidy_string(endpoint.docs),
        operation_id=endpoint.name,
        path_parameters=path_parameters,
        request_schema=_request_schema,
        response_schema=_response_schema,
    )


def extract_path_parameters(url: str) -> Tuple[str, dict]:

    # convert URL from metadata-style to openapi-style
    url = url.replace("<", "{").replace(">", "}")

    # get individual instances of `{...}`
    raw_parameters = set(re.findall(r"\{[^}]*}", url))
    # originally the simpler r"\{.*?}" but SonarLint tells me this approach is safer
    # it translates as open-curly, zero-or-more-not-close-curly, close-curly
    # https://rules.sonarsource.com/python/type/Code%20Smell/RSPEC-5857

    # extract types from parameters, then
    # re-insert parameters into openapi-style url
    parameters = {}
    for raw in raw_parameters:
        p = raw[1:-1]
        c = p.count(":")

        # skip duplicate parameter names
        if p in parameters.keys():
            continue

        # if no type is defined, use str
        if c == 0:
            parameters[p] = "str"

        # if type is defined, use that
        elif c == 1:
            [_param, _type] = p.split(":")
            parameters[_param] = _type
            url = url.replace(raw, "{" + _param + "}")

        # otherwise, skip badly formed parameters
        else:
            continue

    return url, parameters


def dump(metadata: APIMetadata, stream=None):
    oas = OasRoot31()

    _title = "None"
    try:
        [_title] = list(metadata.services.keys())
    except (TypeError, ValueError):
        logging.warning(
            "Could not extract service title from metadata. Expected exactly one valid title."
        )
    finally:
        oas.info.title = _title
        oas.info.description = _title

    oas.info.version = "0.0." + str(metadata.current_version)
    tags = set()

    for service_group in metadata.services.values():
        for api_group in service_group.values():
            for endpoint in api_group.values():
                try:
                    [method] = endpoint.methods
                    method = str.lower(method)
                    tidy_url, path_parameters = extract_path_parameters(endpoint.url)
                    operation = convert_endpoint_to_operation(endpoint, path_parameters)
                    tags.update(set(operation.tags))
                    path = OasPath()
                    path.operation[method] = operation
                    oas.paths[tidy_url] = path
                except (TypeError, ValueError):
                    logging.warning(
                        f"Skipping {service_group}, {api_group}, {endpoint} because method is invalid."
                        f" Expected exactly one method."
                    )

    for tag in tags:
        oas.tags.append({"name": tag})

    return yaml.safe_dump(
        _to_dict(oas), stream, default_flow_style=False, encoding=None
    )
