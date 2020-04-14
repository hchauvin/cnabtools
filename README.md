# Tools around the CNAB specification (see https://cnab.io)

This repo includes:

- [docker2](./drivers/docker2): a CNAB driver that gives more extensive access to the host
machine than the existing `docker` driver in Duffle.
- [bundler](./cnabtools/cnabtools/bundler.py): A toolkit and Command-Line Interface to
build CNAB applications from Duffle specifications, in a more reproducible way.  What
this does is it uses Buildkit instead of Docker to have reproducible builds of the invocation
images.
- [docker](./cnabtools/cnabtools/docker.py): A toolkit and Command-Line Interface to
use Docker/Buildkit in a reproducible way.  We include, among other things, the ability
to simply tag Docker images in a content-addressable fashion and to do "client-side" caching
of Docker builds, that is, not even send the build context to the Docker daemon if
a content-addressable image has already been cached in the daemon.  This can save a lot of
time if the build context is large.

The tools are organized in a Python package.  It can be installed this way:

```bash
pip3 install -e ./cnabtools
```

And the tools can be invoked using `python3 -m`:

```bash
python3 -m cnabtools.bundler --help
```