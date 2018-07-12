# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).
from __future__ import unicode_literals
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from builtins import open, str
from future.utils import PY2

import os
import sys
import textwrap

import fixtures

from acceptable import _service


def clean_up_module(name, old_syspath=None):
    if PY2:
        if isinstance(name, str):
            name = name.encode('utf8')

    sys.modules.pop(name)
    _service.clear_metadata()

    if old_syspath is not None:
        sys.path = old_syspath


class CleanUpModuleImport(fixtures.Fixture):
    def __init__(self, name):
        self.name = name

    def _setUp(self):
        _service.clear_metadata()
        self.addCleanup(clean_up_module, self.name)


class TemporaryModuleFixture(fixtures.Fixture):
    """Setup a module that can be imported, and clean up afterwards."""

    def __init__(self, name, code):
        self.name = name
        self.code = textwrap.dedent(code).strip()
        self.path = None

    def _setUp(self):
        tempdir = self.useFixture(fixtures.TempDir()).path
        self.path = os.path.join(tempdir, '{}.py'.format(self.name))
        with open(self.path, 'w') as f:
            f.write(self.code)

        # preserve state
        old_sys_path = sys.path
        sys.path = [tempdir] + old_sys_path
        _service.clear_metadata()

        self.addCleanup(clean_up_module, self.name, old_sys_path)
