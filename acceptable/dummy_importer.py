# Copyright 2019 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).
import importlib.abc
import importlib.util
import sys
from unittest.mock import MagicMock


class DummyFinder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """Implements PEP 451 module finder and loader which will pretend to
    load modules but actually just create mocks that look like them.

    This allows python code to be loaded when its dependencies are not
    installed.

    allowed_real_modules is a list of module names to not mock instead the
    module finders are tried.

    finders can come from sys.meta_path

    modules in passthrough will raise the correct error on import if
    they can't be loaded.

    This class is used by DummyImporterContext which patches sys.modules
    and sys.meta_path.
    """

    def __init__(self, allowed_real_modules, finders):
        self.finders = finders
        self.allowed = set(allowed_real_modules)

    def find_spec(self, fullname, path, target=None):
        if fullname in self.allowed:
            for finder in self.finders:
                spec = finder.find_spec(fullname, path, target)
                if spec is not None:
                    return spec
            else:
                return None

        return importlib.util.spec_from_loader(fullname, self)

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        mod = MagicMock()
        mod.__file__ = "<DummyFinder>"
        mod.__loader__ = self
        mod.__path__ = []
        mod.__package__ = module.__name__
        mod.__doc__ = "DummyImporterContext dummy"
        mod.__spec__ = module.__spec__

        sys.modules[module.__name__] = mod


class DummyImporterContext(object):
    """Creates a context in which modules, other than those in
    allowed_real_modules, will not be imported but instead replaced with
    mocks.

    Manager sys.modules so that the mock modules are removed after
    the context ends.

    Allows python code to be imported and executed even when its
    dependencies are not installed.
    """

    def __init__(self, *allowed_real_modules):
        self.allowed_real_modules = set(allowed_real_modules)

    def __enter__(self):
        self.orig_sys_meta_path = sys.meta_path
        self.orig_sys_modules = sys.modules
        self.finder = DummyFinder(self.allowed_real_modules, self.orig_sys_meta_path)
        sys.modules = dict(sys.modules)
        sys.meta_path = [self.finder]

    def __exit__(self, *args):
        sys.meta_path = self.orig_sys_meta_path
        sys.modules = self.orig_sys_modules
