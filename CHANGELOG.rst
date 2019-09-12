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
