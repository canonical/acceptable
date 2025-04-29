import difflib
import inspect
import pprint
import re
import sys
import textwrap
from collections import OrderedDict


def get_callsite_location(depth=1):
    frame = sys._getframe(depth + 1)
    return {
        "filename": inspect.getsourcefile(frame),
        "lineno": frame.f_lineno,
        "module": inspect.getmodule(frame),
    }


def get_function_location(fn):
    # get the innermost wrapped function (the view itself)
    while getattr(fn, "__wrapped__", None) is not None:
        fn = fn.__wrapped__

    source_lines, start_line = inspect.getsourcelines(fn)

    # unfortunately because getsourcelines considers decorators to be part of the
    # function, we need to manually find the line that contains the actual `def <...>(`
    # part.
    def_pattern = re.compile(r"^\s*def\s+\w+\s*\(")
    for offset, line in enumerate(source_lines):
        if def_pattern.match(line):
            return {
                "filename": inspect.getsourcefile(fn),
                "lineno": start_line + offset,
                "module": inspect.getmodule(fn),
            }

    # if we can't find a function definition, we just return whatever line Python thinks
    # is the start of the function.
    return {
        "filename": inspect.getsourcefile(fn),
        "lineno": start_line,
        "module": inspect.getmodule(fn),
    }


def clean_docstring(docstring):
    """Dedent docstring, special casing the first line."""
    docstring = docstring.strip()
    if "\n" in docstring:
        # multiline docstring
        if docstring[0].isspace():
            # whole docstring is indented
            return textwrap.dedent(docstring)
        else:
            # first line not indented, rest maybe
            first, _, rest = docstring.partition("\n")
            return first + "\n" + textwrap.dedent(rest)
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
        yield schema


def sort_schema(schema):
    sorted_schema = OrderedDict(_sort_schema(schema))
    # ensure sorting the schema does not alter it
    if schema != sorted_schema:
        d1 = pprint.pformat(schema).splitlines()
        d2 = pprint.pformat(sorted_schema).splitlines()
        diff = "\n".join(difflib.ndiff(d1, d2))
        raise RuntimeError("acceptable: sorting schema failed:\n" + diff)
    return sorted_schema
