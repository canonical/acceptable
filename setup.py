#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).

from setuptools import find_packages, setup


VERSION = "0.38"


setup(
    name="acceptable",
    version=VERSION,
    description="API metadata and schema tool for generating tests and documentation",
    author="Canonical Online Services",
    author_email="online-services@lists.canonical.com",
    url="https://github.com/canonical/acceptable",
    license="LGPLv3",
    packages=find_packages(exclude=["examples", "*tests"]),
    long_description="".join(open("README.rst").readlines()[2:]),
    long_description_content_type="text/x-rst",
    install_requires=["jsonschema", "pyyaml", "Jinja2"],
    extras_require=dict(flask=["Flask"], django=["django>=2.1,<3"]),
    test_suite="acceptable.tests",
    include_package_data=True,
    entry_points={
        "console_scripts": [
            "build_service_doubles = acceptable._build_doubles:main",
            "acceptable = acceptable.__main__:main",
        ]
    },
)
