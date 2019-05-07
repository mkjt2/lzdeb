# LZDeb - build debian packages the lazy way


### Installation

1. [Install Python 3](https://docs.python-guide.org/starting/installation/)
1. [Install Docker](https://docs.docker.com/install/)
1. [Install the pip package](https://pip.pypa.io/en/stable/):
```bash
$ pip3 install lzdeb
```

Tested on MacOS.  Probably works on Linux as well.

### Usage

Prepare a directory `/d` containing:
1. `/d/config.yml`
1. `/d/install`

Run:
```bash
$ lzdeb build /d
```

Collect the resulting debian package file in your working directory.

See `examples/` for details.

```bash
$ lzdeb build examples/ripgrep
...
$ ls *.deb
ripgrep_11.0.1-1_amd64.deb
```

### How To Contribute

* Fork the repo.
* In a [virtualenv](https://virtualenv.pypa.io/en/latest/#):
   * `pip3 install -r requirements.txt`
   * `pip3 install -r .circleci/test_requirements`
* _Hack Away!_
* Testing:
   * New unit tests to go in `test/`
   * If you have [CircleCI](https://circleci.com) access, make sure the `test_all` workflow passes.
   * Otherwise, you could run tests manually (see `.circleci/config.yml`):
      * unit tests: `py.test --cov=lzdeb test/`
      * lint: `pylint -E lzdeb test`
      * pep8: `pycodestyle lzdeb test`
      * type hint checking: `mypy lzdeb test`

