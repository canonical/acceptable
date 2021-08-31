# Copyright 2019 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).
import sys
from unittest.mock import MagicMock


class DummyFinder(object):
    """Implements PEP 302 module finder and loader which will pretend to
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

    def find_module(self, fullname, path=None):
        if fullname in self.allowed:
            for finder in self.finders:
                loader = finder.find_module(fullname, path)
                if loader is not None:
                    return loader
            else:
                return None
        return self

    def load_module(self, fullname):
        try:
            return sys.modules[fullname]
        except KeyError:
            pass
        mod = MagicMock()
        sys.modules[fullname] = mod
        mod.__file__ = "<DummyFinder>"
        mod.__loader__ = self
        mod.__path__ = []
        mod.__package__ = fullname
        mod.__doc__ = "DummyImporterContext dummy"
        return mod


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
