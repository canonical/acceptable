from acceptable import AcceptableService

service = AcceptableService("mysvc")

foo_api = service.api("/foo", "foo", introduced_at=2)

foo_api.request_schema = {
    "type": "object",
    "required": ["foo", "baz"],
    "properties": {
        "foo": {
            "type": "string",
        },
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
        "foo_result": {"type": "string"},
        "bar": {
            "type": "string",
            "description": "bar bar",
            "introduced_at": 5,
        },
    },
}

foo_api.changelog(5, "Added baz field.")
foo_api.changelog(4, "Added bar field")


@foo_api
def foo():
    """Documentation goes here."""
