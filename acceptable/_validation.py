# Copyright 2017-2020 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).
import json
import functools

import jsonschema

from acceptable.util import get_callsite_location, sort_schema


class DataValidationError(Exception):
    """Raises when a request body fails validation."""

    def __init__(self, error_list):
        self.error_list = error_list

    def __repr__(self):
        return "DataValidationError: %s" % ", ".join(self.error_list)

    def __str__(self):
        return repr(self)


def validate_params(schema):
    """Validate the request parameters.

    The request parameters (request.args) are validated against the schema.

    The root of the schema should be an object and each of its properties
    is a parameter.

    An example usage might look like this::

        from snapstore_schemas import validate_params


        @validate_params({
            "type": "object",
            "properties": {
                "id": {
                    "type": "string",
                    "description": "A test property.",
                    "pattern": "[0-9A-F]{8}",
                }
            },
            required: ["id"]
        })
        def my_flask_view():
            ...

    """
    location = get_callsite_location()
    def decorator(fn):
        validate_schema(schema)
        wrapper = wrap_request_params(fn, schema)
        record_schemas(
            fn, wrapper, location, params_schema=sort_schema(schema))
        return wrapper
    return decorator


def wrap_request_params(fn, schema):
    from flask import request
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        error_list = validate(request.args, schema)
        if error_list:
            raise DataValidationError(error_list)
        return fn(*args, **kwargs)
    return wrapper


def validate_body(schema):
    """Validate the body of incoming requests for a flask view.

    An example usage might look like this::

        from snapstore_schemas import validate_body


        @validate_body({
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'snap_id': {'type': 'string'},
                    'series': {'type': 'string'},
                    'name': {'type': 'string'},
                    'title': {'type': 'string'},
                    'keywords': {
                        'type': 'array',
                        'items': {'type': 'string'}
                    },
                    'summary': {'type': 'string'},
                    'description': {'type': 'string'},
                    'created_at': {'type': 'string'},
                },
                'required': ['snap_id', 'series'],
                'additionalProperties': False
            }
        })
        def my_flask_view():
            # view code here
            return "Hello World", 200

    All incoming request that have been routed to this view will be matched
    against the specified schema. If the request body does not match the schema
    an instance of `DataValidationError` will be raised.

    By default this will cause the flask application to return a 500 response,
    but this can be customised by telling flask how to handle these exceptions.
    The exception instance has an 'error_list' attribute that contains a list
    of all the errors encountered while processing the request body.
    """
    location = get_callsite_location()

    def decorator(fn):
        validate_schema(schema)
        wrapper = wrap_request(fn, schema)
        record_schemas(
            fn, wrapper, location, request_schema=sort_schema(schema))
        return wrapper

    return decorator


def wrap_request(fn, schema):
    from flask import request

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        payload = request.get_json(silent=True, cache=True, force=True)
        # If flask can't parse the payload, we want to return a sensible
        # error message, so we try and parse it ourselves. Setting silent
        # to False above isn't good enough, as the generated error message
        # is not informative enough.
        if payload is None:
            try:
                payload = json.loads(request.data.decode(request.charset))
            except ValueError as e:
                raise DataValidationError([
                    "Error decoding JSON request body: %s" % str(e)])
        error_list = validate(payload, schema)
        if error_list:
            raise DataValidationError(error_list)
        return fn(*args, **kwargs)

    return wrapper


def record_schemas(
        fn, wrapper, location, request_schema=None, response_schema=None, params_schema=None):
    """Support extracting the schema from the decorated function."""
    # have we already been decorated by an acceptable api call?
    has_acceptable = hasattr(fn, '_acceptable_metadata')

    if params_schema is not None:
        wrapper._params_schema = params_schema
        wrapper._params_schema_location = location
        if has_acceptable:
            fn._acceptable_metadata._params_schema = params_schema
            fn._acceptable_metadata._params_schema_location = location

    if request_schema is not None:
        # preserve schema for later use
        wrapper._request_schema = wrapper._request_schema = request_schema
        wrapper._request_schema_location = location
        if has_acceptable:
            fn._acceptable_metadata._request_schema = request_schema
            fn._acceptable_metadata._request_schema_location = location

    if response_schema is not None:
        # preserve schema for later use
        wrapper._response_schema = wrapper._response_schema = response_schema
        wrapper._response_schema_location = location
        if has_acceptable:
            fn._acceptable_metadata._response_schema = response_schema
            fn._acceptable_metadata._response_schema_location = location


def validate_output(schema):
    """Validate the body of a response from a flask view.

    Like `validate_body`, this function compares a json document to a
    jsonschema specification. However, this function applies the schema to the
    view response.

    Instead of the view returning a flask response object, it should instead
    return a Python list or dictionary. For example::

        from snapstore_schemas import validate_output

        @validate_output({
            'type': 'object',
            'properties': {
                'ok': {'type': 'boolean'},
            },
            'required': ['ok'],
            'additionalProperties': False
        }
        def my_flask_view():
            # view code here
            return {'ok': True}

    Every view response will be evaluated against the schema. Any that do not
    comply with the schema will cause DataValidationError to be raised.
    """
    location = get_callsite_location()

    def decorator(fn):
        validate_schema(schema)
        wrapper = wrap_response(fn, schema)
        record_schemas(
            fn, wrapper, location, response_schema=sort_schema(schema))
        return wrapper

    return decorator


def wrap_response(fn, schema):
    from flask import current_app, jsonify

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        result = fn(*args, **kwargs)
        if isinstance(result, tuple):
            resp = result[0]
        else:
            resp = result
        if not isinstance(resp, (list, dict)):
            raise ValueError(
                "Unknown response type '%s'. Supported types are list "
                "and dict." % type(resp))

        if current_app.config.get('ACCEPTABLE_VALIDATE_OUTPUT', True):
            error_list = validate(resp, schema)

            assert not error_list,\
                "Response does not comply with output schema: %r.\n%s"\
                % (error_list, resp)

        if isinstance(result, tuple):
            return (jsonify(resp), ) + result[1:]
        else:
            return jsonify(result)
    return wrapper


def validate(payload, schema):
    """Validate `payload` against `schema`, returning an error list.

    jsonschema provides lots of information in it's errors, but it can be a bit
    of work to extract all the information.
    """
    v = jsonschema.Draft4Validator(
        schema, format_checker=jsonschema.FormatChecker())
    error_list = []
    for error in v.iter_errors(payload):
        message = error.message
        location = '/' + '/'.join([str(c) for c in error.absolute_path])
        error_list.append(message + ' at ' + location)
    return error_list


def validate_schema(schema):
    """Validate that 'schema' is correct.

    This validates against the jsonschema v4 draft.

    :raises jsonschema.SchemaError: if the schema is invalid.
    """
    jsonschema.Draft4Validator.check_schema(schema)
