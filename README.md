# LZDeb - build Debian packages the lazy way

Want to install something from a debian / apt package but prebuilt packages don't exist?

_Build your own, the easy (and lazy) way!_

### Usage

Run (/d is a directory):
```bash
$ lzdeb build /d
```

Collect the resulting debian package file in your working directory.


```bash
$ lzdeb build /d
...
$ ls *.deb
```

#### Directory `/d` should contain these files:
1. `/d/config.yml`
1. (optional) `/d/build`
1. `/d/install`
1. (optional) `/d/validate`

#### Example: `examples/silversearcher-ag`

Create a debian package for [the silver searcher](https://github.com/ggreer/the_silver_searcher.git).

##### `lzdeb.yml`
```yaml
builder:
  image: ubuntu:16.04
  bootstrap_cmds:
    - apt update
    - apt install -y git
validator:
  image: ubuntu:18.04
  bootstrap_cmds:
    - apt update
source:
  type: git
  url: https://github.com/ggreer/the_silver_searcher.git
  ref: 2.2.0
  pull_submodules: yes
deb_info:
  pkgname: silversearcher-ag
  pkgversion: 2.2.0
  pkgrelease: 1
  pkglicense: Apache 2.0
  pkggroup: main
  maintainer: example@lzdeb.invalid
  description: "A code-searching tool similar to ack, but faster. http://geoff.greer.fm/ag/"
  requires:
    - liblzma-dev>=5.1.1
    - libpcre3-dev>=2:8.38
    - zlib1g-dev>=1:1.2.8
```

`builder` defines the docker container within which the deb package is built.

`validator` defines the docker container within which the built deb is validated (install the package, may be some test commands)

`source` defines where to get the source code to be built.

`deb_info` defines debian package metadata to be used when creating the debian package.

##### 1. `build`

Install build tools and required libraries.  Build (compile) the code.
```bash
#!/usr/bin/env bash

set -e

apt-get update
apt-get install -y \
  automake \
  pkg-config \
  libpcre3-dev \
  zlib1g-dev \
  liblzma-dev

cd the_silver_searcher*/
./build.sh
```

##### 2. `install`

Perform a "make install".  A debian package is built automatically based on filesystem changes.
```bash
#!/usr/bin/env bash

set -e

cd the_silver_searcher*/
make install
```

##### 3. `validate`

Try installing the built debian package.  Verify program runs.
```bash
#!/usr/bin/env bash

set -e

apt install -y ./*.deb
ag -h
```

##### Tying it all together
```bash
$ lzdeb build example/silversearcher-ag
... spin up build container
...
... build script gets run
...
... install script gets run (deb package file created)
...
... validate script gets run (deb package file gets installed in fresh container)
...
$ ls *.deb
silversearcher-ag_2.2.0-1_amd64.deb
```

### Installation

1. [Install Python 3](https://docs.python-guide.org/starting/installation/)
1. [Install Docker](https://docs.docker.com/install/)
1. [Install the pip package](https://pip.pypa.io/en/stable/):
```bash
$ pip3 install lzdeb
```

Tested on MacOS.  Probably works on Linux as well.

### Caveats

There are many!

We will populate this section with the most important ones, as users report them.

### How To Contribute

* Fork the repo.
* In a [virtualenv](https://virtualenv.pypa.io/en/latest/#):
   * `pip3 install -r requirements.txt`
   * `pip3 install -r .circleci/test_requirements`
* _Hack Away!_
* Testing:
   * New unit tests to go in `test/`
   * If you have [CircleCI](https://circleci.com) access, make sure the `test_all` workflow passes.
   * Otherwise, you could run tests locally (see `.circleci/config.yml`):
      * unit tests: `py.test --cov=lzdeb test/`
      * lint: `pylint -E lzdeb test`
      * pep8: `pycodestyle lzdeb test`
      * type hint checking: `mypy lzdeb test`

