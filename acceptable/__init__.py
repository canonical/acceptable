# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).


# including this causes issues with type types in __all__, which need to be
# native strings, so we explicitly do not want unicode literals here
# from __future__ import unicode_literals
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from ._service import (  # NOQA
    AcceptableService,
    get_metadata,
)
from ._validation import (  # NOQA
    DataValidationError,
    validate_body,
    validate_output,
)


# __all__ strings must be bytes in py2 and unicode in py3
__all__ = [
    'AcceptableService',
    'DataValidationError',
    'get_metadata',
    'validate_body',
    'validate_output',
]
