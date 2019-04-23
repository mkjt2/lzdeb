#!/usr/bin/env python3

import setuptools

with open("README.md", "r") as f:
    long_description = f.read()

import lzdeb

setuptools.setup(
    name="lzdeb",
    version=lzdeb.__version__,
    author="Jackie Tung",
    author_email="jackie.tung@gmail.com",
    description="LzDeb - Build debian packages the lazy way",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/mkjt2/lzdeb",
    packages=['lzdeb'],
    scripts=['scripts/lzdeb'],
    # TODO keep this in sync with requirements.txt
    install_requires=[
        "PyYAML",
        "docker"
    ],
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Operating System :: MacOS :: MacOS X",
        "Programming Language :: Python :: 3"
    ],
)
