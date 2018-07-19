# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).

from __future__ import unicode_literals
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from builtins import *  # NOQA
__metaclass__ = type

import logging

import django
from djangojsonschema.jsonschema import DjangoFormToJSONSchema

from acceptable._service import AcceptableAPI

logger = logging.getLogger('acceptable')

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
            RegexURLPattern,
            RegexURLResolver,
            LocaleRegexURLResolver,
            get_resolver,
        )
    except ImportError:
        from django.core.urlresolvers import (
            RegexURLPattern,
            RegexURLResolver,
            LocaleRegexURLResolver,
            get_resolver,
        )

    PATTERNS = (RegexURLPattern,)
    RESOLVERS = (RegexURLResolver, LocaleRegexURLResolver)

    def get_pattern(p):
        return p.regex.pattern


class EagerDjangoFormToJSONSchema(DjangoFormToJSONSchema):
    """Evaluate lazy translation field text to strings for validation."""

    def convert_formfield(self, name, field, json_schema):
        details = super().convert_formfield(name, field, json_schema)
        # force evaluation of lazy translated text
        details['title'] = str(details['title'])
        details['description'] = str(details['description'])
        return details


_urlmap = None


def get_urlmap():
    global _urlmap
    if _urlmap is None:
        resolver = get_resolver()
        _urlmap = dict(urlmap(resolver.url_patterns))
    return _urlmap


def urlmap(patterns, prefix=None):
    """Recursively build a set of name, url pairs.

    The urls are joined with any prefixes, and cleaned up of extraneous regex
    specific syntax."""
    if prefix is None:
        prefix = ''
    else:
        prefix = '/' + prefix.lstrip('/')

    for pattern in patterns:
        url = prefix + get_pattern(pattern).lstrip('^')
        if isinstance(pattern, PATTERNS):
            yield pattern.name, url.rstrip('$')
        elif isinstance(pattern, RESOLVERS):
            subpatterns = pattern.url_patterns
            for name, rule_url in urlmap(subpatterns, url):
                yield name, rule_url


class DjangoAPI(AcceptableAPI):

    def __init__(
            self,
            name,
            introduced_at,
            options={},
            location=None,
            undocumented=False):
        super().__init__(
            name, None, introduced_at, options, location, undocumented)

        self._form = None
        self.handler_class = None

    def resolve_url(self):
        url = get_urlmap().get(self.name)
        # TODO should we error out if there is no map with that name?
        return url

    @property
    def methods(self):
        default = ['GET']
        if 'methods' in self.options:
            return self.options.get('methods', default)

        return getattr(self.handler_class, 'allowed_methods', default)

    @property
    def django_form(self):
        return self._form

    @django_form.setter
    def django_form(self, form):
        self._form = form

        schema = EagerDjangoFormToJSONSchema().convert_form(form)
        self.request_schema = schema

    def handler(self, handler_class):
        self.handler_class = handler_class
        if self.docs is None and handler_class.__doc__:
            self.docs = handler_class.__doc__.strip()
        return handler_class
