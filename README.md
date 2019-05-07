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

### Contributions are welcome

This is a brand new project - the following areas need some love:

* Test coverage (unit / functional).
* Check the TODOs.
* Verify that this works on Linux
* Improve this README
