[![Build Status](https://travis-ci.org/canonical-ols/acceptable.svg?branch=master)](https://travis-ci.org/canonical-ols/acceptable)
[![Coverage Status](https://coveralls.io/repos/github/canonical-ols/acceptable/badge.svg?branch=master)](https://coveralls.io/github/canonical-ols/acceptable?branch=master)
# acceptable

Acceptable builds on top of [flask](http://flask.pocoo.org/) and adds several
opinionated features designed to make it easier to build a product from several
small services.

## Design Goals:

Acceptable is designed to solve several common problems when building a product
composed of several individual services. Specifically, the library contains the
following high-level features:

 - API endpoints are versioned using the `Accept:` HTTP header. Acceptable
   handles calling the correct view according to a simple version resolution
   protocol.

- Views can be tagged with 'API flags', providing a way to test
  under-development views in a production environment. This opens the door to
  a more regular, predictable feature development velcoty.

- View input and output is validated using
  [jsonschema](http://json-schema.org/). This allows views to express their
  inputs and outputs in a concise manner.

  - These input and output definitions can be extracted from your various
    services and compiled into a library of service doubles, which facilitates
    easy inter-service interaction testing.
