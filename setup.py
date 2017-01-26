#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).

import pkg_resources
from setuptools import setup


VERSION = '0.3'


def parse_requirements_file(path):
    """Parse a requirements file, return a list of requirements as strings."""
    with open(path, 'r') as rfile:
        deps = []
        for requirement in rfile.readlines():
            if requirement.isspace():
                continue
            deps.append(
                pkg_resources.Requirement.parse(requirement).project_name)
        return deps


setup(
    name='acceptable',
    version=VERSION,
    description='API version negotiation for flask-based web services.',
    author='Canonical Online Services',
    author_email='online-services@lists.canonical.com',
    license='LGPLv3',
    packages=['acceptable'],
    install_requires=parse_requirements_file('requirements.txt'),
    test_suite='acceptable.test_acceptable',
    tests_require=parse_requirements_file('requirements-dev.txt')
)
