# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).

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


from future.standard_library import install_aliases
install_aliases()


__all__ = [
    'AcceptableService',
    'DataValidationError',
    'get_metadata',
    'validate_body',
    'validate_output',
]
