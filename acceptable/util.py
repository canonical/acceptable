import inspect


def get_callsite_location(depth=1):
    frame = inspect.stack()[depth + 1]
    return {
        'filename': frame.filename,
        'lineno': frame.lineno,
    }
