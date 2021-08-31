from collections import OrderedDict
import difflib
import inspect
import pprint
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


def _sort_schema(schema):
    """Recursively sorts a JSON schema by dict key."""

    if isinstance(schema, dict):
        for k, v in sorted(schema.items()):
            if isinstance(v, dict):
                yield k, OrderedDict(_sort_schema(v))
            elif isinstance(v, list):
                yield k, list(_sort_schema(v))
            else:
                yield k, v
    elif isinstance(schema, list):
        for v in schema:
            if isinstance(v, dict):
                yield OrderedDict(_sort_schema(v))
            elif isinstance(v, list):
                yield list(_sort_schema(v))
            else:
                yield v
    else:
        yield d


def sort_schema(schema):
    sorted_schema = OrderedDict(_sort_schema(schema))
    # ensure sorting the schema does not alter it
    if schema != sorted_schema:
        d1 = pprint.pformat(schema).splitlines()
        d2 = pprint.pformat(sorted_schema).splitlines()
        diff = '\n'.join(difflib.ndiff(d1, d2))
        raise RuntimeError('acceptable: sorting schema failed:\n' + diff)
    return sorted_schema
