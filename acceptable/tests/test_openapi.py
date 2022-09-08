# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).
from dataclasses import dataclass

import testtools

from acceptable import openapi
from acceptable._service import APIMetadata

EXPECTED_EMPTY_METADATA = """components_schemas: {}
info:
  contact:
    email: ''
    name: ''
  description: ''
  tags: []
  title: ''
  version: ''
openapi: 3.1.0
paths: {}
servers: {}
"""


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


class OpenApiTests(testtools.TestCase):
    def test_dump_of_empty_metadata(self):
        metadata = APIMetadata()
        result = openapi.dump(metadata).splitlines(keepends=False)
        expected = EXPECTED_EMPTY_METADATA.splitlines(keepends=False)
        self.assertListEqual(expected, result)
