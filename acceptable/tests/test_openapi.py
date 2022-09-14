# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).
from dataclasses import dataclass

import testtools

from acceptable import openapi
from acceptable._service import APIMetadata, AcceptableAPI, AcceptableService


@dataclass
class SampleWithImplicitDunderDict(object):
    value: int = 42


@dataclass
class SampleWithToDictMethod(object):
    value: int = 42

    def _to_dict(self):
        return {"sample": self.value}


class ToDictTests(testtools.TestCase):
    @staticmethod
    def test_convert_sample_with_to_dict_method_calls_method():
        result = openapi._to_dict(SampleWithToDictMethod())
        assert {"sample": 42} == result

    @staticmethod
    def test_convert_dict_returns_new_dict():
        source = {"foo": "bar"}
        result = openapi._to_dict(source)
        assert source == result
        assert id(source) != id(result)

    @staticmethod
    def test_convert_list_returns_new_list():
        source = ["fizz", "buzz"]
        result = openapi._to_dict(source)
        assert source == result
        assert id(source) != id(result)

    @staticmethod
    def test_convert_sample_with_dunder_dict_returns_dunder_value():
        result = openapi._to_dict(SampleWithImplicitDunderDict())
        assert {"value": 42} == result

    @staticmethod
    def test_convert_str_returns_same_value():
        result = openapi._to_dict("beeblebrox")
        assert "beeblebrox" == result


class TidyStringTests(testtools.TestCase):
    @staticmethod
    def test_none():
        assert "None" == openapi.tidy_string(None)

    @staticmethod
    def test_empty():
        assert "" == openapi.tidy_string("")

    @staticmethod
    def test_tidy_returns_tidy():
        assert "simple" == openapi.tidy_string("simple")

    @staticmethod
    def test_collapse_two_spaces():
        assert "hello world" == openapi.tidy_string("hello  world")

    @staticmethod
    def test_collapse_three_spaces():
        assert "hello world" == openapi.tidy_string("hello   world")

    @staticmethod
    def test_strip_trailing_spaces():
        assert "hello world" == openapi.tidy_string(" hello world ")


class GetHeadTests(testtools.TestCase):
    def test_empty(self):
        self.assertIsNone(openapi.get_head_of_single_item_list([], "item"))

    @staticmethod
    def test_single_item_list():
        assert "HEAD" == openapi.get_head_of_single_item_list(["HEAD"], "item")

    def test_multiple_item_list_returns_none(self):
        self.assertIsNone(
            openapi.get_head_of_single_item_list(["HEAD", "TAIL"], "item")
        )


class EndpointToOperationTests(testtools.TestCase):
    @staticmethod
    def test_blank():
        endpoint = AcceptableAPI(
            introduced_at=1,
            name="test name",  # maps to operation.operation_id
            service=AcceptableService(name="test service"),
            url="https://test.example",
        )
        operation = openapi.convert_endpoint_to_operation(endpoint)
        assert "None" == operation.description
        assert "test name" == operation.operation_id
        assert operation.summary is None
        assert 1 == len(operation.tags)
        assert "none" == operation.tags[0]

    @staticmethod
    def test_populated():
        endpoint = AcceptableAPI(
            introduced_at=1,
            name="test name",  # maps to operation.operation_id
            service=AcceptableService(
                name="test service",
                group="test group",  # maps to operation.tags
            ),
            title="test title",  # maps to operation.summary
            url="https://test.example",
        )
        endpoint.docs = "test docs"  # maps to operation.description
        operation = openapi.convert_endpoint_to_operation(endpoint)
        assert "test docs" == operation.description
        assert "test name" == operation.operation_id
        assert "test title" == operation.summary
        assert 1 == len(operation.tags)
        assert "test group" == operation.tags[0]


class OpenApiTests(testtools.TestCase):
    def test_dump_of_empty_metadata(self):
        metadata = APIMetadata()
        result = openapi.dump(metadata).splitlines(keepends=True)
        with open("examples/oas_empty_expected.yaml", "r") as _expected:
            expected = _expected.readlines()
        self.assertListEqual(expected, result)
