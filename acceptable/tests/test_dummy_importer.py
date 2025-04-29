# Copyright 2019 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).
import importlib.abc
import importlib.util
import sys
import types

import testtools
from testtools.assertions import assert_that
from testtools.matchers import Contains, Is, Not

from acceptable.dummy_importer import DummyImporterContext


class DummyImporterContextTests(testtools.TestCase):
    def test_mock_fake_import(self):
        with DummyImporterContext():
            import zzzxxxvvv  # noqa

    def test_allowed_real_modules(self):
        class FakeModuleLoader(importlib.abc.MetaPathFinder, importlib.abc.Loader):
            def __init__(self):
                self.imported = False
                self.module = types.SimpleNamespace()

            def find_spec(self, fullname, path, target=None):
                if fullname == "zzzxxxvvv.test":
                    return importlib.util.spec_from_loader(fullname, self)
                return None

            def create_module(self, spec):
                return None

            def exec_module(self, module):
                self.imported = True
                sys.modules[module.__name__] = self.module
                self.module.__name__ = module.__name__
                self.module.__loader__ = self
                self.module.__spec__ = module.__spec__

        fml = FakeModuleLoader()
        sys.meta_path.insert(0, fml)
        with DummyImporterContext("zzzxxxvvv.test"):
            import zzzxxxvvv.test

            assert_that(fml.module, Is(zzzxxxvvv.test))
        assert_that(sys.modules, Not(Contains("zzzxxxvvv.test")))
        assert_that(fml.imported, Is(True))
        sys.meta_path.remove(fml)
