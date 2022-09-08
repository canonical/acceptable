# Copyright 2019 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).
import json
from io import StringIO

from acceptable import generate_doubles
import testtools


class GenerateDoublesTests(testtools.TestCase):
    def test_generate_service_mock_doubles_from_example(self):
        stream = StringIO()
        with open("examples/current_api.json") as f:
            metadata = json.load(f)
            generate_doubles.generate_service_mock_doubles(metadata, stream=stream)
            self.assertIn("foo_1_0 = service_mock", stream.getvalue())
            # check generated code is valid
            exec(stream.getvalue(), {}, {})
