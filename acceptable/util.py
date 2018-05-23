import inspect
import sys


def get_callsite_location(depth=1):
    frame = sys._getframe(depth + 1)
    return {
        'filename': inspect.getsourcefile(frame),
        'lineno': frame.f_lineno,
    }
