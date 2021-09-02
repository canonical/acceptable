# Copyright 2019 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).
import responses


class ResponsesManager(object):
    """The responses library is used to add mock behaviour into the requests
    library.

    It does this using the RequestsMock class, however only one of
    these can be active at a time. Attempting to start a new RequestsMock
    will remove any others hooked into requests.

    We use an instance of this class to manage use of the RequestsMock
    instance `responses.mock`. This allows us to start, stop and reset
    the it at the right time.
    """
    def __init__(self):
        self._attached = 0

    def attach(self):
        if self._attached == 0:
            responses.mock.start()
        self._attached += 1

    def detach(self):
        self._attached -= 1
        assert self._attached >= 0
        if self._attached == 0:
            responses.mock.stop()
            responses.mock.reset()

    def attach_callback(self, methods, url, callback):
        for method in methods:
            responses.mock.add_callback(method, url, callback)
        self.attach()

    def detach_callback(self, methods, url, callback):
        for method in methods:
            responses.mock.remove(method, url)
        self.detach()


responses_manager = ResponsesManager()


class responses_mock_context(object):
    """Provides access to `responses.mock` in a way that is safe to mix with
    mocks from `acceptable.mocks`.

    Use as a context manager or a decorator:

        def blah():
            with responese_mock_context():
                ...
    Or:

        @responese_mock_context()
        def blah():
            ,,,
    """
    def __enter__(self):
        responses_manager.attach()
        return responses.mock

    def __exit__(self, *args):
        responses_manager.detach()

    def __call__(self, func):
        # responses.get_wrapper creates a function which has the same
        # signature etc.  as `func`. It execs `wrapper_template`
        # in a seperate namespace to do this. See get_wrapper code.
        wrapper_template = """\
def wrapper%(signature)s:
    with responses_mock_context:
        return func%(funcargs)s
"""
        namespace = {'responses_mock_context': self, 'func': func}
        return responses.get_wrapped(func, wrapper_template, namespace)
