#! /usr/bin/env python3

from setuptools import find_packages, setup

#EXCLUDE_FROM_PACKAGES = ["contrib", "docs", "tests*"]

setup (
    name='code64',
    version='0.1',
    author='Morten Perriard',
    author_email='morten@perriard.dk',
    description='a 6502 Python hybrid assembler for C64 cross development',
    python_requires='>=3.6',
    packages=find_packages(),
    package_data={'code64': ['imports/*.py']},
    include_package_data=True,
    keywords=[],
    scripts=[],
    py_modules=['main', 'cpu', 'image', 'music', 'assemble', 'context', 'eval', 'lexer', 'petscii'],
    entry_points={"console_scripts": ["code64=code64.main:main"]},
    zip_safe=False,
)
