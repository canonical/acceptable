"""
Helpers to translate acceptable metadata to OpenAPI specifications (OAS).
"""
import json
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Tuple

import yaml

from acceptable._service import AcceptableAPI, APIMetadata


@dataclass
class OasOperation:
    tags: list
    summary: str
    description: str
    operation_id: str
    request_schema: Any
    response_schema: Any
    path_parameters: dict
    query_parameters: dict

    def _parameters_to_openapi(self):
        # To ensure a stable output we sort the parameter dictionary.
        for key, value in sorted(self.path_parameters.items()):
            yield {
                "name": key,
                "in": "path",
                "required": True,
                "schema": {"type": value},
            }
        for key, value in sorted(self.query_parameters.get("properties", {}).items()):
            yield {
                "name": key,
                "in": "query",
                "required": key in self.query_parameters.get("required", {}),
                "schema": value,
            }

    def _to_dict(self):
        result = {
            "tags": self.tags,
            "description": tidy_string(self.description) or "None.",
            "operationId": self.operation_id,
            "parameters": list(self._parameters_to_openapi()),
        }

        if self.summary:
            result["summary"] = self.summary

        if self.request_schema:
            result["requestBody"] = {
                "content": {"application/json": {"schema": self.request_schema}}
            }

        result["responses"] = {"200": {"description": self.summary or "OK"}}
        if self.response_schema:
            result["responses"]["200"]["content"] = {
                "application/json": {"schema": self.response_schema}
            }

        return result


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
    paths: dict = field(default_factory=lambda: defaultdict(dict))

    def _to_dict(self):
        return {
            "openapi": self.openapi,
            "info": _to_dict(self.info),
            "servers": _to_dict(self.servers),
            "tags": _to_dict(self.tags),
            "paths": _to_dict(self.paths),
        }


def _to_dict(source: Any):
    if hasattr(source, "_to_dict"):
        return source._to_dict()  # noqa
    elif isinstance(source, dict):
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


def convert_endpoint_to_operation(
    endpoint: AcceptableAPI, method: str, path_parameters: dict
):
    _request_schema = None
    if endpoint.request_schema:
        _request_schema = json.loads(json.dumps(endpoint.request_schema))

    _response_schema = None
    if endpoint.response_schema:
        _response_schema = json.loads(json.dumps(endpoint.response_schema))

    query_parameters = {}
    if endpoint.params_schema:
        query_parameters = json.loads(json.dumps(endpoint.params_schema))

    return OasOperation(
        tags=[endpoint.service.group] if endpoint.service.group else [],
        summary=endpoint.title,
        description=tidy_string(endpoint.docs),
        operation_id=f"{endpoint.name}-{method}",
        path_parameters=path_parameters,
        query_parameters=query_parameters,
        request_schema=_request_schema,
        response_schema=_response_schema,
    )


def extract_path_parameters(url: str) -> Tuple[str, dict]:
    # convert URL from metadata-style to openapi-style
    if url is None or url == "":
        url = "/"
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
            "Could not extract service title from metadata. "
            "Expected exactly one valid title."
        )
    finally:
        oas.info.title = _title
        oas.info.description = _title

    oas.info.version = "0.0." + str(metadata.current_version)
    tags = set()

    for service_group in metadata.services.values():
        for api_group in service_group.values():
            for endpoint in api_group.values():
                for method in endpoint.methods:
                    method = str.lower(method)
                    tidy_url, path_parameters = extract_path_parameters(endpoint.url)
                    operation = convert_endpoint_to_operation(
                        endpoint, method, path_parameters
                    )
                    tags.update(set(operation.tags))
                    oas.paths[tidy_url][method] = operation

    for tag in sorted(tags):
        oas.tags.append({"name": tag})

    return yaml.safe_dump(
        _to_dict(oas), stream, default_flow_style=False, encoding=None
    )
