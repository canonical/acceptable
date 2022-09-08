# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).
import argparse
import contextlib
import io
import json
import os
import subprocess
import tempfile
from collections import OrderedDict
from functools import partial

import fixtures
import testtools
import yaml

from acceptable import __main__ as main
from acceptable import get_metadata
from acceptable.tests._fixtures import CleanUpModuleImport, TemporaryModuleFixture


# sys.exit on error, but rather throws an exception, so we can catch that in
# our tests:
class SaneArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise RuntimeError(message)


class ParseArgsTests(testtools.TestCase):
    def test_error_with_no_args(self):
        self.assertRaisesRegex(
            RuntimeError,
            "arguments are required",
            main.parse_args,
            [],
            SaneArgumentParser,
        )

    def test_metadata_requires_files(self):
        self.assertRaisesRegex(
            RuntimeError,
            "arguments are required",
            main.parse_args,
            ["metadata"],
            SaneArgumentParser,
        )

    def test_metadata_parses_files(self):
        args = main.parse_args(["metadata", "foo", "bar"])
        self.assertEqual(["foo", "bar"], args.modules)
        self.assertEqual("metadata", args.cmd)

    def test_render_parses_file(self):
        with tempfile.NamedTemporaryFile("w") as api:
            api.write("hi")
            api.flush()
            args = main.parse_args(["render", "--name=name", api.name])

        self.assertTrue("hi", args.metadata.read())
        self.assertEqual("render", args.cmd)

        args.metadata.close()  # suppresses ResourceWarning

    def test_render_parses_stdin_with_no_metadata(self):
        stdin = io.StringIO("hi")
        args = main.parse_args(["render", "--name=name"], stdin=stdin)
        self.assertEqual("hi", args.metadata.read())

    def test_lint_reads_file(self):
        with tempfile.NamedTemporaryFile("w") as api:
            api.write("hi")
            api.flush()
            args = main.parse_args(["lint", api.name, "foo", "bar"])

        self.assertEqual("hi", args.metadata.read())
        self.assertEqual(args.modules, ["foo", "bar"])

        args.metadata.close()  # suppresses ResourceWarning

    def test_lint_force_without_update(self):
        with tempfile.NamedTemporaryFile("w") as api:
            api.write("hi")
            api.flush()
            self.assertRaisesRegex(
                RuntimeError,
                "--force can only be used with --update",
                main.parse_args,
                ["lint", api.name, "foo", "--force"],
                parser_cls=SaneArgumentParser,
            )


class MetadataTests(testtools.TestCase):
    def test_importing_api_metadata_works(self):
        service = """
            from acceptable import AcceptableService
            service = AcceptableService('myservice', 'group')

            root_api = service.api('/', 'root', introduced_at=1)
            root_api.request_schema = {'type': 'object'}
            root_api.response_schema = {'type': 'object'}
            root_api.params_schema = {'type': 'object'}
            root_api.changelog(4, "changelog")

            @root_api
            def my_view():
                "Documentation."
        """

        fixture = self.useFixture(TemporaryModuleFixture("service", service))
        main.import_metadata(["service"])
        import service as svc_mod  # noqa: we monkey-patched this in the line above

        metadata, locations = get_metadata().serialize()

        self.assertEqual(
            {
                "$version": 4,
                "group": {
                    "title": "Group",
                    "apis": {
                        "root": {
                            "service": "myservice",
                            "api_group": "group",
                            "api_name": "root",
                            "methods": ["GET"],
                            "url": "/",
                            "doc": "Documentation.",
                            "changelog": {4: "changelog"},
                            "request_schema": {"type": "object"},
                            "response_schema": {"type": "object"},
                            "params_schema": {"type": "object"},
                            "introduced_at": 1,
                            "title": "Root",
                        }
                    },
                },
            },
            metadata,
        )

        self.assertEqual(
            {
                "root": {
                    "api": {"filename": fixture.path, "lineno": 4, "module": svc_mod},
                    "changelog": {
                        4: {"filename": fixture.path, "lineno": 8, "module": svc_mod}
                    },
                    "request_schema": {
                        "filename": fixture.path,
                        "lineno": 5,
                        "module": svc_mod,
                    },
                    "response_schema": {
                        "filename": fixture.path,
                        "lineno": 6,
                        "module": svc_mod,
                    },
                    "params_schema": {
                        "filename": fixture.path,
                        "lineno": 7,
                        "module": svc_mod,
                    },
                    "view": {"filename": fixture.path, "lineno": 12, "module": svc_mod},
                }
            },
            locations,
        )

    def test_legacy_api_still_works(self):
        service = """

            from acceptable import *
            service = AcceptableService('service')

            root_api = service.api('/', 'root')
            root_api.changelog(4, "changelog")

            @root_api.view(introduced_at='1.0')
            @validate_body({'type': 'object'})
            @validate_output({'type': 'object'})
            @validate_params({'type': 'object', 'properties': {'test': {'type': 'string'}}})
            def my_view():
                "Documentation."
        """
        fixture = self.useFixture(TemporaryModuleFixture("service", service))

        main.import_metadata(["service"])
        import service as svc_mod  # noqa: we monkey-patched this in the line above

        metadata, locations = get_metadata().serialize()

        self.assertEqual(
            {
                "$version": 4,
                "default": {
                    "title": "Default",
                    "apis": {
                        "root": {
                            "service": "service",
                            "api_group": "default",
                            "api_name": "root",
                            "methods": ["GET"],
                            "url": "/",
                            "doc": "Documentation.",
                            "changelog": {4: "changelog"},
                            "request_schema": {"type": "object"},
                            "response_schema": {"type": "object"},
                            "params_schema": {
                                "type": "object",
                                "properties": {"test": {"type": "string"}},
                            },
                            "introduced_at": 1,
                            "title": "Root",
                        }
                    },
                },
            },
            metadata,
        )

        self.assertEqual(
            {
                "root": {
                    "api": {"filename": fixture.path, "lineno": 4, "module": svc_mod},
                    "changelog": {
                        4: {"filename": fixture.path, "lineno": 5, "module": svc_mod}
                    },
                    "request_schema": {
                        "filename": fixture.path,
                        "lineno": 8,
                        "module": svc_mod,
                    },
                    "response_schema": {
                        "filename": fixture.path,
                        "lineno": 9,
                        "module": svc_mod,
                    },
                    "params_schema": {
                        "filename": fixture.path,
                        "lineno": 10,
                        "module": svc_mod,
                    },
                    "view": {"filename": fixture.path, "lineno": 12, "module": svc_mod},
                }
            },
            locations,
        )


class LoadMetadataTests(testtools.TestCase):
    def metadata(self):
        metadata = OrderedDict()
        metadata["$version"] = 2
        metadata["group"] = dict(apis=dict())
        metadata["group"]["apis"]["api1"] = {
            "api_group": "group",
            "api_name": "api1",
            "methods": ["GET"],
            "url": "/",
            "doc": "doc1",
            "changelog": {2: "change 2", 1: "change 1"},
            "request_schema": {"request_schema": 1},
            "response_schema": {"response_schema": 2},
            "introduced_at": 1,
            "title": "Api1",
        }
        return metadata

    def test_load_json_metadata(self):
        json_file = tempfile.NamedTemporaryFile("w")
        json.dump(self.metadata(), json_file)
        json_file.flush()

        # json converts int keys to string
        with open(json_file.name) as fd:
            json_dict = json.load(fd)
        self.assertEqual(
            json_dict["group"]["apis"]["api1"]["changelog"],
            {"1": "change 1", "2": "change 2"},
        )

        with open(json_file.name) as fd:
            result = main.load_metadata(fd)

        self.assertEqual(
            result["group"]["apis"]["api1"]["changelog"], {1: "change 1", 2: "change 2"}
        )


def builder_installed():
    return subprocess.call(["which", "documentation-builder"]) == 0


class RenderMarkdownTests(testtools.TestCase):
    page = main.TEMPLATES.get_template("api_group.md.j2")
    index = main.TEMPLATES.get_template("index.md.j2")

    def metadata(self):
        metadata = OrderedDict()
        metadata["$version"] = 2
        metadata["group"] = dict(apis=dict())
        metadata["group"]["apis"]["api1"] = {
            "api_group": "group",
            "api_name": "api1",
            "methods": ["GET"],
            "url": "/",
            "doc": "doc1",
            "changelog": {"1": "change"},
            "request_schema": {"request_schema": 1},
            "response_schema": {"response_schema": 2},
            "introduced_at": 1,
            "title": "Api1",
        }
        metadata["group"]["apis"]["api2"] = {
            "api_group": "group",
            "api_name": "api1",
            "methods": ["GET"],
            "url": "/",
            "doc": "doc2",
            "changelog": {"2": "2nd change"},
            "request_schema": {"request_schema": 1},
            "response_schema": {"response_schema": 2},
            "introduced_at": 1,
            "title": "Api2",
        }
        return metadata

    def test_render_markdown_success(self):
        args = main.parse_args(["render", "examples/api.json", "--name=SERVICE"])

        with contextlib.closing(args.metadata):
            iterator = main.render_markdown(self.metadata(), args)
            output = OrderedDict((str(k), v) for k, v in iterator)

            self.assertEqual(
                {"en/group.md", "en/index.md", "en/metadata.yaml", "metadata.yaml"},
                set(output),
            )

            top_level_md = yaml.safe_load(output["metadata.yaml"])
            self.assertEqual(
                {"site_title": "SERVICE Documentation: version 2"}, top_level_md
            )

            md = yaml.safe_load(output["en/metadata.yaml"])
            self.assertEqual(
                {
                    "navigation": [
                        {"location": "index.md", "title": "Index"},
                        {"location": "group.md", "title": "Group"},
                    ]
                },
                md,
            )

    def test_render_markdown_undocumented(self):
        args = main.parse_args(["render", "examples/api.json", "--name=SERVICE"])
        with contextlib.closing(args.metadata):
            m = self.metadata()
            m["group"]["apis"]["api2"]["undocumented"] = True
            iterator = main.render_markdown(m, args)
            output = OrderedDict((str(k), v) for k, v in iterator)

            self.assertEqual(
                {"en/group.md", "en/index.md", "en/metadata.yaml", "metadata.yaml"},
                set(output),
            )

            self.assertNotIn("api2", output["en/group.md"])

            md = yaml.safe_load(output["en/metadata.yaml"])
            self.assertEqual(
                {
                    "navigation": [
                        {"location": "index.md", "title": "Index"},
                        {"location": "group.md", "title": "Group"},
                    ]
                },
                md,
            )

    def test_render_markdown_deprecated_at(self):
        args = main.parse_args(["render", "examples/api.json", "--name=SERVICE"])
        with contextlib.closing(args.metadata):
            m = self.metadata()
            m["group"]["apis"]["api2"]["deprecated_at"] = 2
            iterator = main.render_markdown(m, args)
            output = OrderedDict((str(k), v) for k, v in iterator)

            self.assertEqual(
                {"en/group.md", "en/index.md", "en/metadata.yaml", "metadata.yaml"},
                set(output),
            )

            md = yaml.safe_load(output["en/metadata.yaml"])
            self.assertEqual(
                {
                    "navigation": [
                        {"location": "index.md", "title": "Index"},
                        {"location": "group.md", "title": "Group"},
                    ]
                },
                md,
            )

    def test_render_markdown_multiple_groups(self):
        args = main.parse_args(["render", "examples/api.json", "--name=SERVICE"])
        with contextlib.closing(args.metadata):
            metadata = self.metadata()
            metadata["group2"] = {
                "apis": {"api2": metadata["group"]["apis"].pop("api2")}
            }
            iterator = main.render_markdown(metadata, args)
            output = OrderedDict((str(k), v) for k, v in iterator)

            self.assertEqual(
                {
                    "en/group.md",
                    "en/group2.md",
                    "en/index.md",
                    "en/metadata.yaml",
                    "metadata.yaml",
                },
                set(output),
            )

            top_level_md = yaml.safe_load(output["metadata.yaml"])
            self.assertEqual(
                {"site_title": "SERVICE Documentation: version 2"}, top_level_md
            )

            md = yaml.safe_load(output["en/metadata.yaml"])
            self.assertEqual(
                {
                    "navigation": [
                        {"location": "index.md", "title": "Index"},
                        {"location": "group.md", "title": "Group"},
                        {"location": "group2.md", "title": "Group2"},
                    ]
                },
                md,
            )

    def test_render_markdown_group_omitted_with_undocumented(self):
        args = main.parse_args(["render", "examples/api.json", "--name=SERVICE"])
        with contextlib.closing(args.metadata):
            metadata = self.metadata()
            metadata["group2"] = {
                "apis": {"api2": metadata["group"]["apis"].pop("api2")}
            }
            metadata["group2"]["apis"]["api2"]["undocumented"] = True
            iterator = main.render_markdown(metadata, args)
            output = OrderedDict((str(k), v) for k, v in iterator)

            self.assertEqual(
                {"en/group.md", "en/index.md", "en/metadata.yaml", "metadata.yaml"},
                set(output),
            )

            top_level_md = yaml.safe_load(output["metadata.yaml"])
            self.assertEqual(
                {"site_title": "SERVICE Documentation: version 2"}, top_level_md
            )

            md = yaml.safe_load(output["en/metadata.yaml"])
            self.assertEqual(
                {
                    "navigation": [
                        {"location": "index.md", "title": "Index"},
                        {"location": "group.md", "title": "Group"},
                    ]
                },
                md,
            )

    def test_render_cmd_with_templates(self):
        markdown_dir = self.useFixture(fixtures.TempDir())
        with tempfile.NamedTemporaryFile("w") as metadata:
            with tempfile.NamedTemporaryFile("w", dir=os.getcwd()) as template:
                metadata.write(json.dumps(self.metadata()))
                metadata.flush()

                template.write("TEMPLATE")
                template.flush()
                name = os.path.relpath(template.name)

                args = main.parse_args(
                    [
                        "render",
                        metadata.name,
                        "--name=SERVICE",
                        "--dir={}".format(markdown_dir.path),
                        "--page-template=" + name,
                        "--index-template=" + name,
                    ]
                )
                main.render_cmd(args)

        p = partial(os.path.join, markdown_dir.path)
        with open(p("en/group.md")) as f:
            self.assertEqual(f.read(), "TEMPLATE")
        with open(p("en/index.md")) as f:
            self.assertEqual(f.read(), "TEMPLATE")

    @testtools.skipIf(not builder_installed(), "documentation-builder not installed")
    def test_render_cmd_with_documentation_builder(self):
        # documentation-builder is a strict snap, can only work out of $HOME
        home = os.environ["HOME"]
        markdown_dir = self.useFixture(fixtures.TempDir(rootdir=home))
        html_dir = self.useFixture(fixtures.TempDir(rootdir=home))

        with tempfile.NamedTemporaryFile("w") as metadata:
            metadata.write(json.dumps(self.metadata()))
            metadata.flush()

            args = main.parse_args(
                [
                    "render",
                    metadata.name,
                    "--name=SERVICE",
                    "--dir={}".format(markdown_dir.path),
                ]
            )
            main.render_cmd(args)

        build = [
            "documentation-builder",
            "--base-directory={}".format(markdown_dir.path),
            "--output-path={}".format(html_dir.path),
        ]
        try:
            subprocess.check_output(build)
        except subprocess.CalledProcessError as e:
            print(e.output)
            raise

        p = partial(os.path.join, html_dir.path)
        self.assertTrue(os.path.exists(p("en/group.html")))
        self.assertTrue(os.path.exists(p("en/index.html")))


EXPECTED_LINT_OUTPUT = [
    ("examples/api.py", 7, " Error: API foo at request_schema.required"),
    ("examples/api.py", 7, " Warning: API foo at request_schema.foo.description"),
    (
        "examples/api.py",
        25,
        " Warning: API foo at response_schema.foo_result.description",
    ),
    (
        "examples/api.py",
        25,
        " Documentation: API foo at response_schema.foo_result.introduced_at",
    ),
]


class LintTests(testtools.TestCase):
    def test_basic_api_changes(self):
        self.useFixture(CleanUpModuleImport("examples.api"))

        args = main.parse_args(["lint", "examples/api.json", "examples.api"])

        output = io.StringIO()
        result = main.lint_cmd(args, stream=output)
        self.assertEqual(1, result)
        lines = output.getvalue().splitlines()

        for actual, expected in zip(lines, EXPECTED_LINT_OUTPUT):
            self.assertIn(":".join(map(str, expected)), actual)

    def test_openapi_output(self):
        self.useFixture(CleanUpModuleImport("examples.oas_testcase"))

        # Given the collection of files "examples/oas_testcase.*"
        # When we perform a lint-update
        args = main.parse_args(
            [
                "lint",
                "--update",
                "examples/oas_testcase_api.json",
                "examples.oas_testcase",
            ]
        )

        output = io.StringIO()
        result = main.lint_cmd(args, stream=output)

        # Then we exit without error
        self.assertEqual(0, result)

        # And there is no content in the output
        self.assertEqual([], output.getvalue().splitlines())

        # And the OpenAPI file contains the expected value
        with open("examples/oas_testcase_openapi.yaml", "r") as _result:
            result = _result.readlines()

        with open("examples/oas_expected.yaml", "r") as _expected:
            expected = _expected.readlines()

        self.assertListEqual(expected, result)

        # And we implicitly assume the files have not changed


class VersionTests(testtools.TestCase):
    def test_version(self):
        self.useFixture(CleanUpModuleImport("examples.api"))

        args = main.parse_args(["api-version", "examples/api.json", "examples.api"])

        output = io.StringIO()
        result = main.version_cmd(args, stream=output)
        self.assertEqual(0, result)
        self.assertEqual("examples/api.json: 2\nexamples.api: 5\n", output.getvalue())
