Version Next

 * Drop service doubles and mocks, and ``acceptable doubles``. Use the OpenAPI spec with tools such as Connexion instead.

Version 0.39

 * Assorted fixes and improvements in generated OpenAPI specs
 * Extend generated OpenAPI specs with support for query params (fixes #149)
 * Code cleanup with `flake8`
 * Reformat code with `isort`

Version 0.38

 * Add new Django command ``openapi``. Generates ``openapi.yaml``
 * Update format when a single endpoint supports multiple methods.
 * 📢 Please note! operationId now includes both the endpoint name and the method. For example, ``validation-get`` instead of ``validation``. This allows multiple methods on a single endpoint, such as ``validation-post`` and ``validation-get``.

Version 0.37

 * Sort tags to stabilise YAML order
 * Fix OpenAPI spec output when a single endpoint supports multiple methods

Version 0.36

 * Codebase is blackened
 * ``lint --create`` will also generate a valid but incomplete ``openapi.yaml``:

   * includes paths, methods, path parameters, request schema, response schema
   * operations include operationId, description and summary (if found)
   * group names are included as tags
   * version is given as 0.0.V where V is the version number

Version 0.33

 * Drop support for Python < 3.8, so only Ubuntu 20.04 LTS and 22.04 LTS.

Version 0.27

 * Improvements to the includable make file.

Version 0.26

 * Adds an includable make file fragement. See README.rst.

Version 0.25

 * Fix for v0.24 which couldn't be uploaded to PyPI due to README.rst parsing issue

Version 0.24

 * ``acceptable doubles`` generates mocks from metadata;
 * ``acceptable doubles --new-style`` mocks with more features;
 * ``acceptable metadata --dummy-dependencies`` lets you extract metadata in a less complex and more reliable way.

Version 0.23

 * Actuall order all changelog versions numerically, rather than rerelease an old version

Version 0.22

 * Order all changelog versions numerically

Version 0.21

 * Order versions numerically

Version 0.20

 * APIs metadata and documentation rendered in groups, rather than individual
   API. This may require manually updating any api metadata files you use for
   linting.
 * Include module docstring in API group page
 * Can specifiy human friendly titles for apis and groups.
 * Fix url escaping in docs
 * Ordering of metadata now based on import order, rather than alphabetical

Version 0.19

 * fix version bug in rendering
 * support deprecated apis

Verison 0.18

 * Fix packaging bug that excluded django packages
 * More robust django form handling, with more rigorous tests

Version 0.17

 * make acceptable a django app, for better django integration (#60)
 * support overriding the documentation templates/extension (#61, #62)

Version 0.16

 * py2 support (#53)
 * Support same-file reference resolution when building doubles with AST (#57)
 * Make flask an optional dependency (#58)
 * initial django support (#59)

Version 0.15

 * Sort changelogs properly in docs
 * Add global changelog
 * Support undocumented apis
