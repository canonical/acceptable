# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).
import logging

import django
from django.forms import widgets, fields

from acceptable._service import AcceptableAPI
from acceptable.util import clean_docstring, sort_schema

logger = logging.getLogger('acceptable')
_urlmap = None

if django.VERSION >= (2, 0):
    from django.urls import (
        URLPattern,
        URLResolver,
        get_resolver,
    )
    PATTERNS = (URLPattern,)
    RESOLVERS = (URLResolver,)

    def get_pattern(p):
        return str(p.pattern)
else:
    try:
        from django.urls import (
            LocaleRegexURLResolver,
            RegexURLPattern,
            RegexURLResolver,
            get_resolver,
        )
    except ImportError:
        from django.core.urlresolvers import (
            LocaleRegexURLResolver,
            RegexURLPattern,
            RegexURLResolver,
            get_resolver,
        )

    PATTERNS = (RegexURLPattern,)
    RESOLVERS = (RegexURLResolver, LocaleRegexURLResolver)

    def get_pattern(p):
        return p.regex.pattern


def get_urlmap():
    global _urlmap
    if _urlmap is None:
        resolver = get_resolver()
        _urlmap = dict(urlmap(resolver.url_patterns))
    return _urlmap


def urlmap(patterns):
    """Recursively build a map of (group, name) => url patterns.

    Group is either the resolver namespace or app name for the url config.

    The urls are joined with any prefixes, and cleaned up of extraneous regex
    specific syntax."""
    for pattern in patterns:
        group = getattr(pattern, 'namespace', None)
        if group is None:
            group = getattr(pattern, 'app_name', None)
        path = '/' + get_pattern(pattern).lstrip('^').rstrip('$')
        if isinstance(pattern, PATTERNS):
            yield (group, pattern.name), path
        elif isinstance(pattern, RESOLVERS):
            subpatterns = pattern.url_patterns
            for (_, name), subpath in urlmap(subpatterns):
                yield (group, name), path.rstrip('/') + subpath


def get_field_schema(name, field):
    """Returns a JSON Schema representation of a form field."""
    field_schema = {
        'type': 'string',
    }

    if field.label:
        field_schema['title'] = str(field.label)  # force translation

    if field.help_text:
        field_schema['description'] = str(field.help_text)  # force translation

    if isinstance(field, (fields.URLField, fields.FileField)):
        field_schema['format'] = 'uri'
    elif isinstance(field, fields.EmailField):
        field_schema['format'] = 'email'
    elif isinstance(field, fields.DateTimeField):
        field_schema['format'] = 'date-time'
    elif isinstance(field, fields.DateField):
        field_schema['format'] = 'date'
    elif isinstance(field, (fields.DecimalField, fields.FloatField)):
        field_schema['type'] = 'number'
    elif isinstance(field, fields.IntegerField):
        field_schema['type'] = 'integer'
    elif isinstance(field, fields.NullBooleanField):
        field_schema['type'] = 'boolean'
    elif isinstance(field.widget, widgets.CheckboxInput):
        field_schema['type'] = 'boolean'

    if getattr(field, 'choices', []):
        field_schema['enum'] = sorted([choice[0] for choice in field.choices])

    # check for multiple values
    if isinstance(field.widget, (widgets.Select, widgets.ChoiceWidget)):
        if field.widget.allow_multiple_selected:
            # promote to array of <type>, move details into the items field
            field_schema['items'] = {
                'type': field_schema['type'],
            }
            if 'enum' in field_schema:
                field_schema['items']['enum'] = field_schema.pop('enum')
            field_schema['type'] = 'array'

    return field_schema


def get_form_schema(form):
    """Return a JSON Schema object for a Django Form."""
    schema = {
        'type': 'object',
        'properties': {},
    }

    for name, field in form.base_fields.items():
        schema['properties'][name] = get_field_schema(name, field)
        if field.required:
            schema.setdefault('required', []).append(name)

    return schema


class DjangoAPI(AcceptableAPI):
    """Django-flavour API metadata

    Supports setting a Django form to provide json schema for documentation, as
    well providing an API handler class to inspect for more metadata.
    """

    def __init__(
            self,
            service,
            name,
            introduced_at,
            options={},
            location=None,
            undocumented=False,
            deprecated_at=None,
            title=None):
        # leave url blank, as we can't know it until django has set itself up
        # properly
        super().__init__(
            service,
            name,
            None,
            introduced_at,
            options,
            location,
            undocumented,
            deprecated_at,
            title,
        )

        self._form = None
        self.handler_class = None

    def resolve_url(self):
        name = self.name
        try_default = True

        if ':' in self.name:
            group, name = self.name.split(':', 2)
            try_default = False  # user passed explicit group, just use that
        else:
            group = self.service.group

        urlmap = get_urlmap()
        url = urlmap.get((group, name))
        if url is None and try_default:
            url = urlmap.get((None, name))
        # TODO should we error out if there is no map with that name?
        return url

    @property
    def methods(self):
        default = ['GET']
        if 'methods' in self.options:
            return list(self.options.get('methods', default))

        # allowed_methods works for piston handlers
        # TODO: add support for DRF? And maybe plain view functions with
        # decorators?
        return list(getattr(self.handler_class, 'allowed_methods', default))

    @property
    def django_form(self):
        return self._form

    @django_form.setter
    def django_form(self, form):
        self._form = form
        schema = get_form_schema(form)
        self.request_schema = sort_schema(schema)

    def handler(self, handler_class):
        """Link to an API handler class (e.g. piston or DRF)."""
        self.handler_class = handler_class
        # we take the docstring from the handler class, not the methods
        if self.docs is None and handler_class.__doc__:
            self.docs = clean_docstring(handler_class.__doc__)
        return handler_class
