"""Test case for OpenAPI specification (OAS) output."""

from acceptable import AcceptableService

service = AcceptableService("OpenApiSample")

foo_api = service.api("/foo/<p:int>/<q>", "foo", introduced_at=2)

foo_api.params_schema = {
    "type": "object",
    "required": ["param1"],
    "properties": {
        "param1": {"type": "string"},
        "param2": {"type": "integer"},
    },
}

foo_api.request_schema = {
    "type": "object",
    "required": ["foo", "baz"],
    "properties": {
        "foo": {"description": "This is a foo.", "type": "string"},
        "baz": {
            "type": "object",
            "description": "Bar the door.",
            "introduced_at": 4,
            "properties": {
                "bar": {"type": "string", "introduced_at": 5, "description": "asdf"}
            },
        },
    },
}

foo_api.response_schema = {
    "type": "object",
    "properties": {
        "foo_result": {"description": "Result of a foo.", "type": "string"},
        "bar": {"type": "string", "description": "bar bar", "introduced_at": 5},
    },
}

foo_api.changelog(5, "Added baz field.")
foo_api.changelog(4, "Added bar field")


@foo_api
def foo():
    """Documentation goes here."""
