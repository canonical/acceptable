# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).
import json
import sys

from fixtures import Fixture
from testtools import TestCase
from testtools.matchers import StartsWith
import jsonschema

import flask

from acceptable._validation import (
    DataValidationError,
    validate_body,
    validate_output,
)


class FlaskValidateBodyFixture(Fixture):
    def __init__(self, body_schema=None, output_schema=None, view_fn=None):
        if not (body_schema or output_schema):
            raise ValueError(
                "Must specify at least one of body_schema or output_schema"
            )
        self.body_schema = body_schema
        self.output_schema = output_schema
        self.view = view_fn

    def _setUp(self):
        self.app = flask.Flask(__name__)
        self.app.testing = True

        def _default_view():
            return "OK", 200

        self.view = self.view or _default_view

        if self.body_schema:
            self.view = validate_body(self.body_schema)(self.view)
        if self.output_schema:
            self.view = validate_output(self.output_schema)(self.view)

        self.app.route("/", methods=["POST"])(self.view)
        self.client = self.app.test_client()

    def post_json(self, json_payload):
        return self.client.post(
            "/",
            data=json.dumps(json_payload),
            headers={"Content-Type": "application/json"},
        )


class ValidateBodyTests(TestCase):
    def test_raises_on_bad_schema(self):
        def fn():
            pass

        self.assertRaises(
            jsonschema.SchemaError, validate_body({"required": "bar"}), fn
        )

    def test_passes_on_good_payload(self):
        app = self.useFixture(FlaskValidateBodyFixture({"type": "object"}))

        resp = app.post_json(dict(foo="bar"))
        self.assertEqual(200, resp.status_code)

    def test_raises_on_bad_payload(self):
        app = self.useFixture(FlaskValidateBodyFixture({"type": "object"}))

        e = self.assertRaises(DataValidationError, app.post_json, [])
        msg = "[] is not of type 'object' at /"
        self.assertEqual([msg], e.error_list)

    def test_raises_on_invalid_json(self):
        app = self.useFixture(FlaskValidateBodyFixture({"type": "object"}))

        e = self.assertRaises(
            DataValidationError,
            app.client.post,
            "/",
            data="invalid json",
            headers={"Content-Type": "application/json"},
        )
        # Python 3.3 json decode errors have a different format from later
        # versions, so this check isn't as explicit as I'd like.
        self.assertThat(
            e.error_list[0], StartsWith("Error decoding JSON request body: ")
        )

    def test_validates_even__on_wrong_mimetype(self):
        app = self.useFixture(FlaskValidateBodyFixture({"type": "object"}))

        resp = app.client.post("/", data="{}", headers={"Content-Type": "text/plain"})
        self.assertEqual(200, resp.status_code)

    def test_validates_even_on_missing_mimetype(self):
        app = self.useFixture(FlaskValidateBodyFixture({"type": "object"}))

        resp = app.client.post("/", data="{}", headers={})
        self.assertEqual(200, resp.status_code)


class ValidateOutputTests(TestCase):
    def test_raises_on_bad_schema(self):
        def fn():
            pass

        self.assertRaises(
            jsonschema.SchemaError, validate_output({"required": "bar"}), fn
        )

    def test_raises_on_bad_payload(self):
        def view():
            return []

        app = self.useFixture(
            FlaskValidateBodyFixture(output_schema={"type": "object"}, view_fn=view)
        )

        e = self.assertRaises(AssertionError, app.post_json, [])

        msg = "[] is not of type 'object' at /"

        self.assertEqual(
            "Response does not comply with output schema: %r.\n%s" % ([msg], []), str(e)
        )

    def test_raises_on_unknown_response_type(self):
        def view():
            return object()

        app = self.useFixture(
            FlaskValidateBodyFixture(output_schema={"type": "object"}, view_fn=view)
        )
        e = self.assertRaises(ValueError, app.post_json, {})
        self.assertIn("Unknown response type", str(e))
        self.assertIn("Supported types are list and dict.", str(e))

    def test_skips_validation_if_disabled(self):
        def view():
            return []

        app = self.useFixture(
            FlaskValidateBodyFixture(output_schema={"type": "object"}, view_fn=view)
        )

        # Output validation is enabled by default.
        self.assertRaises(AssertionError, app.post_json, [])

        # But if disabled then the app is trusted to return valid data.
        app.app.config["ACCEPTABLE_VALIDATE_OUTPUT"] = False
        self.assertEqual(b"[]\n", app.post_json([]).data)

        # It can also be explicitly enabled.
        app.app.config["ACCEPTABLE_VALIDATE_OUTPUT"] = True
        self.assertRaises(AssertionError, app.post_json, [])

    def assertResponseJsonEqual(self, response, expected_json):
        data = json.loads(response.data.decode(response.charset))
        self.assertEqual(expected_json, data)

    def test_passes_on_good_payload_single_return_parameter(self):
        returned_payload = {"foo": "bar"}

        def view():
            return returned_payload

        app = self.useFixture(
            FlaskValidateBodyFixture(output_schema={"type": "object"}, view_fn=view)
        )
        resp = app.post_json({})
        self.assertEqual(200, resp.status_code)
        self.assertResponseJsonEqual(resp, returned_payload)

    def test_passes_on_good_payload_double_return_parameter(self):
        returned_payload = {"foo": "bar"}

        def view():
            return returned_payload, 201

        app = self.useFixture(
            FlaskValidateBodyFixture(output_schema={"type": "object"}, view_fn=view)
        )
        resp = app.post_json({})
        self.assertEqual(201, resp.status_code)
        self.assertResponseJsonEqual(resp, returned_payload)

    def test_passes_on_good_payload_triple_return_parameter(self):
        returned_payload = {"foo": "bar"}

        def view():
            return returned_payload, 201, {"Custom-Header": "Foo"}

        app = self.useFixture(
            FlaskValidateBodyFixture(output_schema={"type": "object"}, view_fn=view)
        )
        resp = app.post_json({})
        self.assertEqual(201, resp.status_code)
        self.assertResponseJsonEqual(resp, returned_payload)
        self.assertEqual("Foo", resp.headers["Custom-Header"])


class DeltaValidationErrorTests(TestCase):
    def test_repr_and_str(self):
        e = DataValidationError(["error one", "error two"])
        self.assertEqual("DataValidationError: error one, error two", str(e))
        self.assertEqual(str(e), repr(e))
