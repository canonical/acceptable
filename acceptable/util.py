from __future__ import unicode_literals
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from future import standard_library
standard_library.install_aliases()  # NOQA

import inspect
import sys


def get_callsite_location(depth=1):
    frame = sys._getframe(depth + 1)
    return {
        'filename': inspect.getsourcefile(frame),
        'lineno': frame.f_lineno,
    }
