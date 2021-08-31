# Copyright 2019 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).
from acceptable.dummy_importer import DummyImporterContext
import testtools
from testtools.matchers import Not, Contains, Equals, Is
from testtools.assertions import assert_that
import sys


class DummyImporterContextTests(testtools.TestCase):
    def test_mock_fake_import(self):
        with DummyImporterContext():
            import zzzxxxvvv

    def test_allowed_real_modules(self):
        class FakeModuleLoader(object):
            def __init__(self):
                self.imported = False
                self.module = object()

            def find_module(self, fullname, path=None):
                if fullname == 'zzzxxxvvv.test':
                    return self

            def load_module(self, fullname):
                self.imported = True
                sys.modules[fullname] = self.module
                return self.module
        fml = FakeModuleLoader()
        sys.meta_path.insert(0, fml)
        with DummyImporterContext('zzzxxxvvv.test'):
            import zzzxxxvvv.test
            assert_that(fml.module, Is(zzzxxxvvv.test))
        assert_that(sys.modules, Not(Contains('zzzxxxvvv.test')))
        assert_that(fml.imported, Is(True))
        sys.meta_path.remove(fml)
