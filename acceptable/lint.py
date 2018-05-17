# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).
import os


class Message:
    """A linter message to the user."""
    def __init__(self, name, msg, *args, **kwargs):
        self.name = name
        self.location = kwargs.pop('location', None)
        self.api_name = kwargs.pop('api_name', None)
        self.msg = msg.format(*args, **kwargs)

    def __str__(self):
        output = '{}: {}: {} {}'.format(
            self.api_name,
            self.name,
            self.__class__.__name__,
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


class Error(Message):
    pass


class Warning(Message):
    pass


class Fixit(Message):
    pass


class CheckChangelog(Message):
    def __init__(self, name, revision):
        super().__init__(name, '')
        self.revision = revision


def removed_items(items, target):
    """Iterate through any item in items that is removed from target."""
    for item in items:
        if item not in target:
            yield item


def metadata_lint(old, new, locations):
    """Run the linter over the new metadata, comparing to the old."""
    for removed in set(old) - set(new):
        yield Error('', 'api removed', api_name=removed)

    for name, api in new.items():
        old_api = old.get(name, {})
        api_locations = locations[name]
        for message in lint_api(name, old_api, api, api_locations):
            message.api_name = name
            if message.location is None:
                message.location = api_locations['api']
            yield message


def lint_api(api_name, old, new, locations):
    """Lint an acceptable api metadata."""
    is_new_api = not old
    api_location = locations['api']
    changelog = new.get('changelog', {})
    changelog_location = api_location

    if locations['changelog']:
        changelog_location = list(locations['changelog'].values())[0]

    # apis must have documentation if they are new
    if not new.get('doc'):
        msg_type = Error if is_new_api else Warning
        yield msg_type(
            'doc',
            'missing documentation',
            api_name=api_name,
            location=locations.get('view', api_location)
        )

    introduced_at = new.get('introduced_at')
    if introduced_at is None:
        yield Error(
            'introduced_at', 'missing introduced_at', location=api_location)

    if not is_new_api:
        # cannot change introduced_at if we already have it
        old_introduced_at = old.get('introduced_at')
        if old_introduced_at is not None:
            if old_introduced_at != introduced_at:
                yield Error(
                    'introduced_at',
                    'introduced_at changed from {} to {}',
                    old_introduced_at,
                    introduced_at,
                    api_name=api_name,
                    location=api_location,
                )

    # cannot change url
    if new['url'] != old.get('url', new['url']):
        yield Error(
            'url',
            'url changed from {} to {}',
            old['url'],
            new['url'],
            api_name=api_name,
            location=api_location,
        )

    # cannot add required fields
    for removed in removed_items(old.get('methods', []), new['methods']):
        yield Error(
            'methods',
            'HTTP method {} removed',
            removed,
            api_name=api_name,
            location=api_location,
        )

    for schema in ['request_schema', 'response_schema']:
        new_schema = new.get(schema)
        if new_schema is None:
            continue

        schema_location = locations[schema]
        old_schema = old.get(schema, {})

        for message in walk_schema(
                schema, old_schema, new_schema, root=True, new_api=is_new_api):
            if isinstance(message, CheckChangelog):
                if message.revision not in changelog:
                    yield Fixit(
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
    elif isinstance(schema_type, str):
        return [schema_type]
    else:
        return schema_type


def check_custom_attrs(name, old, new, new_api=False):
    # these are our custom schema properties, not in the jsonschema
    # standard, and we don't need them on the root schema object, as that
    # takes its doc from the function docstring and its introduced_at from
    # the api definition
    if not new.get('doc'):
        yield Warning(name + '.doc', 'missing documentation')

    if not new_api:
        introduced_at = new.get('introduced_at')
        if introduced_at is None:
            yield Warning(name + '.introduced_at', 'missing introduced_at')
        else:
            introduced_at_changed = False
            old_introduced_at = old.get('introduced_at')
            if old_introduced_at is not None:
                introduced_at_changed = old_introduced_at != introduced_at

            if introduced_at_changed:
                yield Error(
                    name + '.introduced_at',
                    'introduced_at changed from {} to {}',
                    old_introduced_at,
                    introduced_at,
                )
            else:
                # we have a specific introduced_at field, make sure to
                # check it's referenced by a changelog entry
                yield CheckChangelog(name, introduced_at)


def walk_schema(name, old, new, root=False, new_api=False):
    if not root:
        yield from check_custom_attrs(name, old, new, new_api)

    types = get_schema_types(new)
    old_types = get_schema_types(old)
    for removed in removed_items(old_types, types):
        yield Error(
            name + '.type',
            'cannot remove type {} from field',
            removed,
        )

    # you cannot add new required fields
    old_required = old.get('required', [])
    for removed in removed_items(new.get('required', []), old_required):
        yield Error(
            name + '.required',
            'Cannot require new field {}',
            removed,
        )

    if 'object' in types:
        properties = new.get('properties', {})
        old_properties = old.get('properties', {})

        for deleted in set(old_properties).difference(properties):
            yield Error(
                name + '.' + deleted, 'cannot delete field {}', deleted)

        for prop, value in sorted(properties.items()):
            yield from walk_schema(
                name + '.' + prop,
                old_properties.get(prop, {}),
                value,
                new_api=new_api,
            )
