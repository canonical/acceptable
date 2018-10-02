from __future__ import unicode_literals
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).
import testtools

from acceptable import util


class UtilsTestCase(testtools.TestCase):

    def test_sort_schema_simple(self):
        srtd = util.sort_schema({
            '5': '5',
            '1': '1',
            '3': '3',
        })
        self.assertEqual(['1','3','5'], list(srtd))

    def test_sort_schema_simple(self):
        d = {'5': '5', '1': '1', '3': '3'}
        l = [5, 1, 3]
        srtd = util.sort_schema({
            'foo': {
                'b': [d],
                'a': [l]
            }
        })

        # check we sort nested dicts
        self.assertEqual(['a','b'], list(srtd['foo']))
        # check we sort dicts nested in lists
        self.assertEqual(['1','3','5'], list(srtd['foo']['b'][0]))
        # ensure we preserve the order of lists
        self.assertEqual([5, 1, 3], list(srtd['foo']['a'][0]))
