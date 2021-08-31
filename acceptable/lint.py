# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).
from enum import IntEnum
import os


class LintTypes(IntEnum):
    WARNING = 0
    DOCUMENTATION = 1
    ERROR = 2


# shortcuts
WARNING = LintTypes.WARNING
DOCUMENTATION = LintTypes.DOCUMENTATION
ERROR = LintTypes.ERROR


class Message():
    """A linter message to the user."""
    level = None

    def __init__(self, name, msg, *args, **kwargs):
        self.name = name
        self.location = kwargs.pop('location', None)
        self.api_name = kwargs.pop('api_name', None)
        self.msg = msg.format(*args, **kwargs)

    def __str__(self):
        output = '{}: API {} at {}: {}'.format(
            self.level.name.title(),
            self.api_name,
            self.name,
            self.msg,
        )

        if self.location is None:
            return output
        else:
            return '{}:{}: {}'.format(
                os.path.relpath(self.location['filename']),
                self.location['lineno'],
                output,
            )


class LintError(Message):
    level = ERROR


class LintWarning(Message):
    level = WARNING


class LintFixit(Message):
    level = DOCUMENTATION


class CheckChangelog(Message):
    def __init__(self, name, revision):
        super().__init__(name, '')
        self.revision = revision


def metadata_lint(old, new, locations):
    """Run the linter over the new metadata, comparing to the old."""
    # ensure we don't modify the metadata
    old = old.copy()
    new = new.copy()
    # remove version info
    old_introduced_at = old.pop('$version', None)
    new.pop('$version', None)

    for old_group_name in old:
        if old_group_name not in new:
            yield LintError('', 'api group removed', api_name=old_group_name)

    for group_name, new_group in new.items():
        old_group = old.get(group_name, {'apis': {}})
        for name, api in new_group['apis'].items():
            old_api = old_group['apis'].get(name, {})
            api_locations = locations[name]
            for message in lint_api(name, old_api, api, api_locations, old_introduced_at):
                message.api_name = name
                if message.location is None:
                    message.location = api_locations['api']
                yield message


def lint_api(api_name, old, new, locations, old_introduced_at):
    """Lint an acceptable api metadata."""
    is_new_api = not old
    api_location = locations['api']
    changelog = new.get('changelog', {})
    changelog_location = api_location

    if locations['changelog']:
        changelog_location = list(locations['changelog'].values())[0]

    # apis must have documentation if they are new
    if not new.get('doc'):
        msg_type = LintError if is_new_api else LintWarning
        yield msg_type(
            'doc',
            'missing docstring documentation',
            api_name=api_name,
            location=locations.get('view', api_location)
        )

    introduced_at = new.get('introduced_at')
    if introduced_at is None:
        yield LintError(
            'introduced_at',
            'missing introduced_at field',
            location=api_location,
        )

    if is_new_api:
        if not isinstance(introduced_at, int):
            yield LintError(
                'introduced_at',
                'introduced_at should be an integer',
                location=api_location,
            )
        if old_introduced_at is not None and introduced_at <= old_introduced_at:
            yield LintError(
                'introduced_at',
                'introduced_at should be > {}'.format(old_introduced_at),
                location=api_location,
            )

    if not is_new_api:
        # cannot change introduced_at if we already have it
        old_introduced_at = old.get('introduced_at')
        if old_introduced_at is not None:
            if old_introduced_at != introduced_at:
                yield LintError(
                    'introduced_at',
                    'introduced_at changed from {} to {}',
                    old_introduced_at,
                    introduced_at,
                    api_name=api_name,
                    location=api_location,
                )

    # cannot change url
    if new['url'] != old.get('url', new['url']):
        yield LintError(
            'url',
            'url changed from {} to {}',
            old['url'],
            new['url'],
            api_name=api_name,
            location=api_location,
        )

    # cannot add required fields
    for removed in set(old.get('methods', [])) - set(new['methods']):
        yield LintError(
            'methods',
            'HTTP method {} removed',
            removed,
            api_name=api_name,
            location=api_location,
        )

    for schema in ['request_schema', 'response_schema']:
        new_schema = new.get(schema)
        if new_schema is None:
            if old.get(schema) is not None:
                yield LintError(
                    schema,
                    '{} schema removed',
                    schema.split('_')[0].title(),
                    api_name=api_name,
                    location=api_location,
                )
            continue

        schema_location = locations[schema]
        old_schema = old.get(schema) or {}

        for message in walk_schema(
                schema, old_schema, new_schema, root=True, new_api=is_new_api):
            if isinstance(message, CheckChangelog):
                if message.revision not in changelog:
                    yield LintFixit(
                        message.name,
                        'No changelog entry for revision {}',
                        message.revision,
                        location=changelog_location,
                    )
            else:
                # add in here, saves passing it down the recursive call
                message.location = schema_location
                yield message


def get_schema_types(schema):
    schema_type = schema.get('type')
    if schema_type is None:
        return []
    elif isinstance(schema_type, (str, bytes)):
        return [schema_type]
    else:
        return schema_type


def check_custom_attrs(name, old, new, new_api=False):
    # these are our custom schema properties, not in the jsonschema
    # standard, and we don't need them on the root schema object, as that
    # takes its doc from the function docstring and its introduced_at from
    # the api definition
    if 'description' not in new:
        yield LintWarning(name + '.description', 'missing description field')

    # New field on existing api without introduced_at
    if not new_api and not old and new.get('introduced_at') is None:
        yield LintFixit(
            '{}.introduced_at'.format(name), 'missing introduced_at field'
        )
    # Existing field but introduced_at has changed
    elif (
        not new_api and
        old.get('introduced_at') is not None and
        old.get('introduced_at') != new.get('introduced_at')
    ):
        yield LintError(
            '{}.introduced_at'.format(name),
            'introduced_at changed from {} to {}',
            old.get('introduced_at'),
            new.get('introduced_at'),
        )
    # Check introduced_at has a change log entry
    elif new.get('introduced_at') is not None:
        yield CheckChangelog(name, new.get('introduced_at'))


def walk_schema(name, old, new, root=False, new_api=False):
    if not root:
        for i in check_custom_attrs(name, old, new, new_api):
            yield i

    types = get_schema_types(new)
    old_types = get_schema_types(old)
    for removed in set(old_types) - set(types):
        yield LintError(
            name + '.type',
            'cannot remove type {} from field',
            removed,
        )

    # you cannot add new required fields to an existing API.
    if not new_api:
        old_required = old.get('required', [])
        for removed in set(new.get('required', [])) - set(old_required):
            yield LintError(
                name + '.required',
                'Cannot require new field {}',
                removed,
            )

    if 'object' in types:
        properties = new.get('properties', {})
        old_properties = old.get('properties', {})

        for deleted in set(old_properties) - set(properties):
            yield LintError(
                name + '.' + deleted, 'cannot delete field {}', deleted)

        for prop, value in sorted(properties.items()):
            for i in walk_schema(
                    name + '.' + prop,
                    old_properties.get(prop, {}),
                    value,
                    new_api=new_api):
                yield i

    if 'array' in types and 'items' in new:
        for i in walk_schema(
                name + '.items',
                old.get('items', {}),
                new['items'],
                new_api=new_api):
            yield i
