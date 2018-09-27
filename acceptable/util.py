from __future__ import unicode_literals
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from builtins import *  # NOQA

import inspect
import sys
import textwrap


def get_callsite_location(depth=1):
    frame = sys._getframe(depth + 1)
    return {
        'filename': inspect.getsourcefile(frame),
        'lineno': frame.f_lineno,
        'module': inspect.getmodule(frame),
    }


def clean_docstring(docstring):
    """Dedent docstring, special casing the first line."""
    docstring = docstring.strip()
    if '\n' in docstring:
        # multiline docstring
        if docstring[0].isspace():
            # whole docstring is indented
            return textwrap.dedent(docstring)
        else:
            # first line not indented, rest maybe
            first, _, rest = docstring.partition('\n')
            return first + '\n' + textwrap.dedent(rest)
    return docstring


