# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).
from collections import defaultdict
from dataclasses import dataclass

import testtools
import yaml

from acceptable import openapi
from acceptable._service import (
    APIMetadata,
    AcceptableAPI,
    AcceptableService,
    clear_metadata,
)


def tearDownModule():
    clear_metadata()


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
    def test_convert_defaultdict_returns_new_dict():
        source = defaultdict(foo="bar")
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
    def test_collapse_newline():
        assert "hello world" == openapi.tidy_string("hello\nworld")

    @staticmethod
    def test_collapse_two_spaces():
        assert "hello world" == openapi.tidy_string("hello  world")

    @staticmethod
    def test_collapse_three_spaces():
        assert "hello world" == openapi.tidy_string("hello   world")

    @staticmethod
    def test_strip_trailing_spaces():
        assert "hello world" == openapi.tidy_string(" hello world ")

    @staticmethod
    def test_collapse_edge_case():
        assert "hello world" == openapi.tidy_string("hello\n world ")


class ParameterExtractionTests(testtools.TestCase):
    def test_blank(self):
        url, parameters = openapi.extract_path_parameters("")
        assert url == "/"
        assert parameters == {}

    def test_no_parameters(self):
        url, parameters = openapi.extract_path_parameters("https://www.example.com")
        assert url == "https://www.example.com"
        assert parameters == {}

    def test_simple_parameter(self):
        url, parameters = openapi.extract_path_parameters(
            "https://www.example.com/<test>"
        )
        assert url == "https://www.example.com/{test}"
        assert parameters == {"test": "str"}

    def test_typed_parameter(self):
        url, parameters = openapi.extract_path_parameters(
            "https://www.example.com/<test:int>"
        )
        assert url == "https://www.example.com/{test}"
        assert parameters == {"test": "int"}

    def test_multiple_typed_parameters(self):
        url, parameters = openapi.extract_path_parameters(
            "https://www.example.com/<test:int>...<test2:float>"
        )
        assert url == "https://www.example.com/{test}...{test2}"
        assert parameters == {"test": "int", "test2": "float"}

    def test_ignore_bad_parameter(self):
        url, parameters = openapi.extract_path_parameters(
            "https://www.example.com/<test:int:float>"
        )
        assert url == "https://www.example.com/{test:int:float}"
        assert parameters == {}


class EndpointToOperationTests(testtools.TestCase):
    @staticmethod
    def test_blank():
        endpoint = AcceptableAPI(
            introduced_at=1,
            name="test-name",  # maps to operation.operation_id
            service=AcceptableService(name="test service"),
            url="https://test.example",
        )
        operation = openapi.convert_endpoint_to_operation(endpoint, "get", {})
        assert "None" == operation.description
        assert "test-name-get" == operation.operation_id
        assert operation.summary is None
        assert 0 == len(operation.tags)

    @staticmethod
    def test_populated():
        endpoint = AcceptableAPI(
            introduced_at=1,
            name="test-name",  # maps to operation.operation_id
            service=AcceptableService(
                name="test service", group="test group"  # maps to operation.tags
            ),
            title="test title",  # maps to operation.summary
            url="https://test.example",
        )
        endpoint.docs = "test docs"  # maps to operation.description
        operation = openapi.convert_endpoint_to_operation(endpoint, "get", {})
        assert "test docs" == operation.description
        assert "test-name-get" == operation.operation_id
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

    def test_single_endpoint_with_multiple_methods(self):
        metadata = APIMetadata()
        service = AcceptableService("service", metadata=metadata)
        foo_api_get = service.api("/foo", "get_foo", methods=["GET"])
        foo_api_post = service.api("/foo", "create_foo", methods=["POST"])

        result = openapi.dump(metadata)
        spec = yaml.safe_load(result)

        assert list(spec["paths"].keys()) == ["/foo"]
        assert list(spec["paths"]["/foo"].keys()) == ["get", "post"]
