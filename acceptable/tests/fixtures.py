# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).
import os
import sys
import textwrap

import fixtures

from acceptable import _service


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
        _service.Metadata.clear()

        self.addCleanup(setattr, sys, 'path', old_sys_path)
        self.addCleanup(sys.modules.pop, self.name)
        self.addCleanup(_service.Metadata.clear)
