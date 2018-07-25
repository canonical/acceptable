# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).
from __future__ import unicode_literals
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from builtins import *  # NOQA

import json
import subprocess
import sys
import os

from django import forms
from testtools import TestCase

from acceptable._service import (
    clear_metadata,
    get_metadata,
)
from acceptable.__main__ import parse_metadata
from acceptable import djangoutil


def setUpModule():
    # This module tests against the django app in examples/django_app, so we
    # set that up and import it
    if 'examples/django_app' not in sys.path:
        sys.path.append('examples/django_app')

    if 'DJANGO_SETTINGS_MODULE' not in os.environ:
        os.environ['DJANGO_SETTINGS_MODULE'] = 'django_app.settings'
    import django
    django.setup()
    djangoutil.get_urlmap()


def tearDownModule():
    if sys.path[-1] == 'examples/django_app':
        sys.path = sys.path[:-1]
    os.environ.pop('DJANGO_SETTINGS_MODULE')
    clear_metadata()


class TestUrlMap(TestCase):

    def test_urlmap_works(self):
        # this test asserts against the urlpatterns defined in:
        # examples/django_app/django_app/views.py
        urlmap = djangoutil.get_urlmap()

        # tests stripping of regex chars
        self.assertEqual(urlmap[None, 'test'], '/test')

        # test regex params
        self.assertEqual(urlmap[None, 'test2'], '/test2/(.*)')

        # tests mutliple namespaces with the same view name
        self.assertEqual(urlmap[None, 'login'], '/login')
        self.assertEqual(urlmap['admin', 'login'], '/prefix1/admin/login/')
        self.assertEqual(urlmap['other', 'login'], '/prefix2/admin/login/')


class TestFormSchema(TestCase):

    def test_get_form_schema_test_form(self):
        from django_app.views import TestForm
        schema = djangoutil.get_form_schema(TestForm)
        expected = {
            'type': 'object',
            'required': ['foo'],
            'properties': {
                'foo': {
                    'title': 'foo',
                    'description': 'foo help',
                    'type': 'string',
                    'format': 'uri',
                },
                'bar': {
                    'title': 'bar',
                    'description': 'bar help',
                    'type': 'string',
                    'enum': ['A', 'B', 'C'],
                },
            },
        }
        self.assertEqual(expected, schema)

    def test_get_field_schema_uri(self):
        field = forms.URLField(label='label', help_text='help')
        self.assertEqual(
            {
                'type': 'string',
                'format': 'uri',
                'title': 'label',
                'description': 'help',
            },
            djangoutil.get_field_schema('name', field),
        )

    def test_get_field_schema_date(self):
        field = forms.DateField(label='label', help_text='help')
        self.assertEqual(
            {
                'type': 'string',
                'format': 'date',
                'title': 'label',
                'description': 'help',
            },
            djangoutil.get_field_schema('name', field),
        )

    def test_get_field_schema_datetime(self):
        field = forms.DateTimeField(label='label', help_text='help')
        self.assertEqual(
            {
                'type': 'string',
                'format': 'date-time',
                'title': 'label',
                'description': 'help',
            },
            djangoutil.get_field_schema('name', field),
        )

    def test_get_field_schema_decimal(self):
        field = forms.DecimalField(label='label', help_text='help')
        self.assertEqual(
            {
                'type': 'number',
                'title': 'label',
                'description': 'help',
            },
            djangoutil.get_field_schema('name', field),
        )

    def test_get_field_schema_integer(self):
        field = forms.IntegerField(label='label', help_text='help')
        self.assertEqual(
            {
                'type': 'integer',
                'title': 'label',
                'description': 'help',
            },
            djangoutil.get_field_schema('name', field),
        )

    def test_get_field_schema_choice(self):
        field = forms.ChoiceField(
            label='label', help_text='help', choices=['A', 'B', 'C'])
        self.assertEqual(
            {
                'type': 'string',
                'title': 'label',
                'description': 'help',
                'enum': ['A', 'B', 'C']
            },
            djangoutil.get_field_schema('name', field),
        )

    def test_get_field_schema_multiple_choice(self):
        field = forms.MultipleChoiceField(
            label='label', help_text='help', choices=['A', 'B', 'C'])
        self.assertEqual(
            {
                'type': 'array',
                'title': 'label',
                'description': 'help',
                'enum': ['A', 'B', 'C']
            },
            djangoutil.get_field_schema('name', field),
        )


def expected_metadata():
    from django_app.views import TestForm
    return {
        '$version': 1,
        'test': {
            'url': '/test',
            'methods': ['POST'],
            'request_schema': djangoutil.get_form_schema(TestForm),
            'response_schema': None,
            'doc': 'Documentation.',
            'changelog': {},
            'introduced_at': 1,
            'api_name': 'test',
            'api_group': None,
            'service': 'django_app',
        },
    }


class TestDjangoAPI(TestCase):

    def test_example_app_works(self):
        metadata = get_metadata()
        api, _ = parse_metadata(metadata)
        self.assertEqual(expected_metadata(), api)


class TestManagementCommands(TestCase):
    # Note: this is located here as it tests all the django stuff, even though
    # the code is not in the djangoutil module

    def test_metadata_command(self):
        cmd = [sys.executable, 'manage.py', 'acceptable', 'metadata']
        output = subprocess.check_output(
            cmd,
            cwd='examples/django_app',
            universal_newlines=True,
        )
        self.assertEqual(expected_metadata(), json.loads(output))

    def test_api_version_command(self):
        cmd = [
            sys.executable,
            'manage.py',
            'acceptable',
            'api-version',
            '../api.json',
        ]
        output = subprocess.check_output(
            cmd,
            cwd='examples/django_app',
            universal_newlines=True,
        )
        self.assertEqual('../api.json: 2\nImported API: 1\n', output)
