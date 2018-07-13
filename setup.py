#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).

from setuptools import setup


VERSION = '0.15'


setup(
    name='acceptable',
    version=VERSION,
    description='API version negotiation for flask-based web services.',
    author='Canonical Online Services',
    author_email='online-services@lists.canonical.com',
    url='https://github.com/canonical-ols/acceptable',
    license='LGPLv3',
    packages=['acceptable'],
    install_requires=[
        'Flask<1.0',
        'future',
        'jinja2',
        'jsonschema',
        'pyyaml',
    ],
    test_suite='acceptable.tests',
    include_package_data=True,
    package_data={
        'acceptable': ['templates/*'],
    },
    entry_points={
        'console_scripts': [
            'build_service_doubles = acceptable._build_doubles:main',
            'acceptable = acceptable.__main__:main',
        ]
    },
)
