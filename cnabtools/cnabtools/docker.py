#!/usr/bin/env python3

"""
Toolkit and Command-Line Interface to use Docker/Buildkit in a reproducible
way.
"""

import argparse
import sys
import os
import subprocess
import json
import hashlib
import logging
import tempfile
import shutil


def content_addressable_imgref(image_repository, image_id):
    """
    Creates a content-addressable image reference for an image with a given
    image ID to store in a given image repository: the resulting image
    reference will uniquely address the content of the image.

    Args:
        image_repository: The repository to use in the image reference.
        image_id: The ID of the image.
    """
    return image_repository + ':' + image_id[image_id.index(':')+1:][:40]


def _imgref_for_invocation_digest(build_context_digest):
    """
    Returns the image reference to tag an image given the digest of its build
    context.

    Such an image reference allows linking together a build context and
    an image.

    Args:
        build_context_digest: The hex digest for the build context.
    Returns:
        An image reference.
    """
    return 'build-context:' + build_context_digest


class Docker:
    def __init__(self, logger_name="docker"):
        self.env = {**os.environ, "DOCKER_BUILDKIT": "1"}

        self.logger = logging.getLogger(logger_name)

    def build_content_addressable(self, build_context_path, image_repository,
                                  **kwargs):
        """
        Builds an image and tag it with its image ID
        so that it becomes content addressable.

        The image is not built if an image was already built with the same build
        context and same arguments.

        The check is done client-side, meaning that in the case of a cache hit
        the build context is not even uploaded to the buildkit daemon.  This can
        save a lot of time if the build context is large.

        Args:
            build_context_path: The path to the build context.
            image_repository: The repository to tag the image with.
            **kwargs: Additional arguments to pass to [[build_with_client_cache]].

        Returns:
            The image reference, i.e. "repository:image_id", where
            image ID is the ID of the image as given by `docker build`.
        """
        image_id = self.build_with_client_cache(build_context_path, **kwargs)
        imgref = self.tag_content_addressable(image_repository, image_id)
        return imgref, image_id

    def tag_content_addressable(self, image_repository, image_id):
        """
        Tags an image with its image ID so that it becomes content addressable.

        Args:
            image_repository: The repository to tag the image with.
            image_id: The image ID.

        Returns:
            The image reference, i.e. "repository:image_id".
        """
        imgref = content_addressable_imgref(image_repository, image_id)
        subprocess.run([
            'docker',
            'tag',
            image_id,
            imgref,
        ])
        return imgref

    def build_with_client_cache(self, build_context_path, iidfile=None, args=None):
        """
        Builds an image using a client cache.

        The image is not built if an image was already built with the same build
        context and same arguments.

        The check is done client-side, meaning that in the case of a cache hit
        the build context is not even uploaded to the buildkit daemon.  This can
        save a lot of time if the build context is large.

        Args:
            build_context_path: Path to the build context.
            iidfile: Path to an output file where to put the image ID (see the
                "--iidfile" argument of "docker build").
            args: Additional arguments to pass to "docker build".  The "--iidfile"
                argument must not be given in "args" but in the "iidfile" keyword
                argument.

        Return:
            The image ID.
        """
        if not args:
            args = []

        build_invocation_digest = self.digest_build_invocation(build_context_path, args)
        imgref = _imgref_for_invocation_digest(build_invocation_digest)
        image_id = self.image_id(imgref)
        if image_id:
            if iidfile:
                with open(iidfile, 'w') as f:
                    f.write(image_id)
            return image_id

        tmpdir = None
        if not iidfile:
            tmpdir = tempfile.mkdtemp()
            iidfile = os.path.join(tmpdir, 'iidfile')

        try:
            subprocess.run(['docker', 'build',
                            '--iidfile', iidfile] + args + [build_context_path],
                           env=self.env,
                           check=True)
            with open(iidfile, 'r') as f:
                iid = f.read().strip()
            subprocess.run(['docker', 'tag', iid, imgref],
                           env=self.env, check=True)
        finally:
            if tmpdir:
                shutil.rmtree(tmpdir)

        return iid

    def digest_build_invocation(self, build_context_path,
                                build_invocation_args=None):
        """
        Digests an invocation to "docker build" by digesting the content
        of the build context and the arguments to pass to "docker build".

        Args:
            build_context_path: Path to the build context.
            build_invocation_args: Arguments passed to "docker build".

        Return:
            A hex digest.
        """

        # Note that .dockerignore is not taken into account.  This means
        # that you have potentially more cache misses than if we took
        # it into account.

        digests = {}
        for dp, dn, filenames in os.walk(build_context_path):
            for f in filenames:
                path = os.path.join(dp, f)
                digests[os.path.relpath(path,
                                        build_context_path)] =\
                    _digest_file(path)
        return _digest_json({
            'digests': digests,
            'args': build_invocation_args,
        })

    def image_id(self, imgref):
        """
        Try to get the image ID for a given image reference.

        Args:
            imgref: The image reference to get the image ID of.

        Return:
            The image ID, or "None" if the image could not be found in the
            buildkit cache.
        """
        p = subprocess.run(['docker', 'inspect', imgref,
                            '--format', '{{ .Id }}'],
                           capture_output=True,
                           encoding='utf8',
                           env=self.env)
        if p.returncode != 0:
            return None
        else:
            return p.stdout.strip()


def _digest_file(file):
    """
    Digests a single file.

    Args:
        file: The path to the file to digest.

    Return:
        A hex digest (a string).
    """
    BUF_SIZE = 65536

    m = hashlib.sha256()
    with open(file, 'rb') as f:
        while True:
            buf = f.read(BUF_SIZE)
            if not buf:
                break
            m.update(buf)

    return m.hexdigest()


def _digest_string(s):
    """
    Digests a string.

    Args:
        s: The string to digest.

    Return:
        A hex digest (a string).
    """
    m = hashlib.sha256()
    m.update(s.encode('utf8'))
    return m.hexdigest()


def _digest_json(o):
    """
    Digests an object after having serializing it to JSON.

    Args:
        o: The object to digest.

    Return:
        A hex digest (a string).
    """
    return _digest_string(json.dumps(o, sort_keys=True))


class CLI:
    """
    Command-Line Interface.
    """

    def __init__(self):
        parser = argparse.ArgumentParser(
            description='Make',
            usage="make <command> [<args>]")
        subcommands = [
            attr for attr in dir(self)
            if not attr.startswith("_") and callable(getattr(self, attr))
        ]
        parser.add_argument('command',
                            help='Subcommand to run: one of: ' + " ".join(
                                subcommands))
        args = parser.parse_args(sys.argv[1:2])
        if not hasattr(self, args.command):
            print('Unrecognized command')
            parser.print_help()
            exit(1)
        getattr(self, args.command)()

    def build(self):
        parser = argparse.ArgumentParser(
            description='Docker build with client-side caching')
        parser.add_argument('path', help='Path to the context')
        parser.add_argument('--iidfile', help='Path to the image id file')
        parser.add_argument('args', help='Other arguments to "docker build"',
                            nargs=argparse.REMAINDER)
        args = parser.parse_args(sys.argv[2:])
        Docker().build_with_client_cache(args.path, args.iidfile, args.args or [])


if __name__ == "__main__":
    try:
        CLI()
    except KeyboardInterrupt as e:
        print("Interrupted")
        sys.exit(1)