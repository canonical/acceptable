# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).

from __future__ import unicode_literals
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from future.utils import text_to_native_str
from future import standard_library
standard_library.install_aliases()  # NOQA

try:
    from pathlib import Path
    Path().expanduser()
except (ImportError, AttributeError):
    from pathlib2 import Path

from ._service import (
    AcceptableService,
    get_metadata,
)
from ._validation import (
    DataValidationError,
    validate_body,
    validate_output,
)


# __all__ must be bytes in py2 and unicode in py3
__all__ = [
    text_to_native_str('AcceptableService'),
    text_to_native_str('DataValidationError'),
    text_to_native_str('get_metadata'),
    text_to_native_str('validate_body'),
    text_to_native_str('validate_output'),
]
