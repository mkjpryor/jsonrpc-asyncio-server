#!/usr/bin/env python3

import os, re
from setuptools import setup, find_namespace_packages


here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'README.md')) as f:
    README = f.read()


if __name__ == "__main__":
    setup(
        name = 'jsonrpc-asyncio-server',
        setup_requires = ['setuptools_scm'],
        use_scm_version = True,
        description = 'Tools for building JSON-RPC servers using asyncio.',
        long_description = README,
        classifiers = [
            "Programming Language :: Python",
        ],
        author = 'Matt Pryor',
        author_email = 'matt.pryor@stfc.ac.uk',
        url = 'https://github.com/mkjpryor/jsonrpc-asyncio-server',
        packages = find_namespace_packages(include = ['jsonrpc.*']),
        include_package_data = True,
        install_requires = ['pydantic', 'jsonrpc-asyncio-model'],
        extras_require = {
            'quart': ['quart'],
        }
    )
