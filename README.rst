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


Includable Makefile
-------------------

*If you are using make files to automate your build you might find this useful.*

The acceptable package contains a make file fragment that can be included to
give you the following targets:

- ``api-lint`` - Checks backward compatibility and version numbers;
- ``api-update-metadata`` - Check like ``api-lint`` then update the saved metadata;
- ``api-version`` - Print the saved metadata and current API version;
- ``api-docs-markdown`` - Generates markdown documentation.

The make file has variables for the following which you can override if
needed:

- ``ACCEPTABLE_ENV`` - The virtual environment with acceptable installed, it defaults to ``$(ENV)``.
- ``ACCEPTABLE_METADATA`` - The saved metadata filename, it defaults to ``api.json``;
- ``ACCEPTABLE_DOCS`` - The directory ``api-docs-markdown`` will generate documentation under, it defaults to ``docs``.

You will need to create a saved metadata manually the first time using
``acceptable metadata`` command and saving it to the value of ``ACCEPTABLE_METADATA``.

The make file assumes the following variables:

- ``ACCEPTABLE_MODULES`` is a space separated list of modules containing acceptable annotated services;
- ``ACCEPTABLE_SERVICE_TITLE`` is the title of the service used by ``api-docs-markdown``.

``ACCEPTABLE_SERVICE_TITLE`` should not be quoted e.g.::

    ACCEPTABLE_SERVICE_TITLE := Title of the Service

To include the file you'll need to get its path, if the above variables and
conditions exist you can put this in your make file::

    include $(shell $(ENV)/bin/python -c 'import pkg_resources; print(pkg_resources.resource_filename("acceptable", "make/Makefile.acceptable"))' 2> /dev/null)

Development
-----------

``make test`` and ``make tox`` should run without errors.

To run a single test module invoke::

    python setup.py test --test-suite acceptable.tests.test_module

or::

    tox -epy38 -- --test-suite acceptable.tests.test_module

...the latter runs "test_module" against Python 3.8 only.
