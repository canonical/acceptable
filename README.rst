|Build Status| |Coverage Status|

==========
acceptable
==========

Acceptable builds on top of `flask <http://flask.pocoo.org/>`__ and adds
several opinionated features designed to make it easier to build a
product from several small services.

Design Goals:
-------------

Acceptable is designed to solve several common problems when building a
product composed of several individual services. Specifically, the
library contains the following high-level features:

-  API endpoints are versioned using the ``Accept:`` HTTP header.
   Acceptable handles calling the correct view according to a simple
   version resolution protocol.

-  Views can be tagged with 'API flags', providing a way to test
   under-development views in a production environment. This opens the
   door to a more regular, predictable feature development velocity.

-  View input and output is validated using
   `jsonschema <http://json-schema.org/>`__. This allows views to
   express their inputs and outputs in a concise manner.

   -  These input and output definitions can be extracted from your various
      services and compiled into a library of service doubles, which
      facilitates easy inter-service interaction testing.

.. |Build Status| image:: https://travis-ci.org/canonical-ols/acceptable.svg?branch=master
   :target: https://travis-ci.org/canonical-ols/acceptable
.. |Coverage Status| image:: https://coveralls.io/repos/github/canonical-ols/acceptable/badge.svg?branch=master
   :target: https://coveralls.io/github/canonical-ols/acceptable?branch=master


Documentation (beta)
--------------------

One of the goals of acceptable is to use the metadata about your api to build documentation.

First, acceptable can parse your code for acceptable metadata, and generate a json version of your api metadata::

    acceptable metadata path/to/files*.py > api.json

Next, acceptable can transform the previously saved metadata into markdown::

    acceptable render api.json --name 'My Service'

You can do this in a single step::

    acceptable metadata path/to/files*.py | acceptable render --name 'My Service'

This markdown is designed to rendered to html by
`documentation-builder <https://docs.ubuntu.com/documentation-builder/en/>`::

    documentation-builder --base-directory docs

