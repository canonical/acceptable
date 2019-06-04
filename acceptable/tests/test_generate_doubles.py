# Copyright 2019 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).
from future import standard_library
standard_library.install_aliases()

import json
from io import StringIO

from acceptable import generate_doubles
import testtools

class GenerateDoublesTests(testtools.TestCase):
    def test_generate_service_mock_doubles_from_example(self):
        stream = StringIO()
        metadata = json.load(open('examples/current_api.json'))
        generate_doubles.generate_service_mock_doubles(metadata, stream=stream)
        self.assertIn('foo_1_0 = service_mock', stream.getvalue())