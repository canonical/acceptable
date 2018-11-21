|Build Status| |Coverage Status|

==========
acceptable
==========

Acceptable is python tool to annotate and capture the metadata around your
python web API. This metadata can be used for validation, documentation,
testing and linting of your API code.

It works standalone, or can be hooked into Flask (beta support for Django) web
apps for richer integration.


Design Goals:
-------------

- Tightly couple code, metadata, and documentation to reduce drift and increase DRY.

- Validation of JSON input and output

- Provide tools for developers to make safe changes to APIs

- Make it easy to generate API documentation.

- Tools for generating testing doubles from the API metadata.


Usage
-----

And example, for flask::

    from acceptable import AcceptableService

    service = AcceptableService('example')

    foo_api = service.api('foo', '/foo', introduced_at=1, methods=['POST'])
    foo_api.request_schema = <JSON Schema...>
    foo_api.response_schema = <JSON Schema...>
    foo_api.changelog(3, 'Changed other thing')
    foo_api.changelog(2, 'Changed something')

    @foo_api
    def view():
        ...

You can use this metadata to bind the URL to a flask app::

    from acceptable import get_metadata()
    app = Flask(__name__)
    get_metadata().bind_all(app)

You can now generate API metadata like so::

    acceptable metadata your.import.path > api.json

This metadata can now be used to generate documentation, and provide API linting.


Django
------

Note: Django support is very limited at the minute, and is mainly for documentation.

Marking up the APIs themselves is a little different::

    from acceptable import AcceptableService

    service = AcceptableService('example')

    # url is looked up from name, like reverse()
    foo_api = service.django_api('app:foo', introduced_at=1)
    foo_api.django_form = SomeForm
    foo_api.changelog(3, 'Changed other thing)
    foo_api.changelog(2, 'Changed something')

    @foo_api.handler
    class MyHandler(BaseHandler):
        allowed_methods=['POST']
        ...

Acceptable will generate a JSON schema representation of the form for documentation.

To generate API metadata, you should add 'acceptable' to INSTALLED_APPS. This
will provide an 'acceptable' management command::


    ./manage.py acceptable metadata > api.json   # generate metadata

And also::

    ./manage.py acceptable api-version api.json  # inspect the current version



Documentation (beta)
--------------------

One of the goals of acceptable is to use the metadata about your API to build documentation.

Once you have your metadata in JSON format, as above, you can transform that into markdown documentation::

    acceptable render api.json --name 'My Service'

You can do this in a single step::

    acceptable metadata path/to/files*.py | acceptable render --name 'My Service'

This markdown is designed to rendered to html by
`documentation-builder <https://docs.ubuntu.com/documentation-builder/en/>`::

    documentation-builder --base-directory docs

