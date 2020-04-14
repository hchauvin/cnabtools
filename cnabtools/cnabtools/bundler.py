#!/usr/bin/env python3
"""
Toolkit and Command-Line Interface to build CNAB applications
from Duffle specifications, in a more reproducible way.
"""

import os
import argparse
import sys
import subprocess
import json
import time
import datetime

from cnabtools.docker import Docker


class DuffleContext:
    """
    Operations on a duffle context.
    """

    def __init__(self, duffle_context_path):
        """
        Args:
            duffle_context_path: The path to the duffle context.  The duffle context
                is a folder that contains a "duffle.json" file and a
                "cnab" folder.
        """
        self.duffle_context_path = duffle_context_path

    @property
    def manifest_path(self):
        return os.path.join(self.duffle_context_path, 'duffle.json')

    def read_manifest(self):
        """
        Reads the manifest found in the "duffle.json" file.

        Return:
            The "duffle.json" file content, deserialized from JSON.
        """
        with open(self.manifest_path, 'r') as f:
            return json.load(f)

    def write_manifest(self, manifest):
        with open(self.manifest_path, 'w') as f:
            json.dump(manifest, f)

    def relocate_images_to_content_addressable(self, image_ids):
        """
        Adds the digests to the images in a duffle.json, and
        relocates the images to make them content-addressable (i.e., the
        tags of the images become content-dependent).

        Relocation involves both modifying the "duffle.json" file to
        put the proper image references, and doing a "docker tag" to have
        buildkit take the image references into account.

        Args:
            image_ids: A map of image names (the keys of the "images" map
                in "duffle.json") to image IDs.  The images whose names are
                not in "image_ids" are not relocated.
        """
        duffle_manifest = self.read_manifest()

        docker = self._docker()

        next_images = {}
        for image_name in duffle_manifest['images']:
            image = duffle_manifest['images'][image_name]
            image_id = image_ids.get(image_name)
            if not image_id:
                next_images[image_name] = image
            else:
                next_image = docker.tag_content_addressable(
                    image['image'], image_id)
                next_images[image_name] = {
                    **image,
                    "image": next_image,
                    "contentDigest": image_id,
                }

        next_duffle_manifest = {
            **duffle_manifest,
            'images': next_images,
        }

        self.write_manifest(next_duffle_manifest)

    def build_cnab_app(self, output_file=None):
        """
        Builds a CNAB app.

        This is equivalent to "duffle build", but uses buildkit instead
        of Docker to build the invocation images.  Using buildkit gives
        reproducible image builds.

        Args:
            path: The path to the duffle context.  The duffle context
                is a folder that contains a "duffle.json" file and a
                "cnab" folder.
            output_file: Where to put the CNAB "bundle.json" that the
                build produces.  If "None", the bundle.json is not
                written.

        Return:
            The content of the "bundle.json" that has been built.
        """
        duffle_manifest = self.read_manifest()

        cnab_dir = os.path.join(self.duffle_context_path, 'cnab')
        app_name = duffle_manifest['name']

        cnab_invocation_images = []
        for name in duffle_manifest['invocationImages']:
            cnab_invocation_images.append(
                self._build_invocation_image(
                    cnab_dir, app_name, name,
                    duffle_manifest['invocationImages'][name]))

        cnab_manifest = {
            **duffle_manifest,
            'invocationImages': cnab_invocation_images,
        }

        if output_file:
            with open(output_file, 'w') as f:
                f.write(canonical_json(cnab_manifest))

        return cnab_manifest

    def _build_invocation_image(self, cnab_dir, app_name, manifest_name,
                                build_spec):
        """
        Builds an invocation image.

        Args:
            cnab_dir: The directory to the CNAB app, i.e., "<duffle context>/cnab".
            app_name: The name of the CNAB app as given in the manifest.
            manifest_name: The name of the image as given in the manifest (manifest
                names are the keys of the "invocationImages" map).
            build_spec: Build specification (build specifications are the values
                of the "invocationImages" map).

        Return:
            The CNAB specification for the invocation image.
        """
        builder = build_spec.get("builder", "docker")
        if builder == 'docker':
            image_full_name = f"{app_name}-{manifest_name}"
            if build_spec.get('configuration', {}).get('registry'):
                image_full_name = (
                    build_spec['configuration']['registry'] + '/' +
                    image_full_name)
            imgref, image_id = (
                self._docker().build_content_addressable(
                    cnab_dir, image_full_name))
            return {
                'image': imgref,
                'contentDigest': image_id,
                'imageType': 'docker',
            }
        else:
            raise Exception(f"builder '{builder}' is not supported")

    def _docker(self):
        """
        Gets a Docker object to interact with Docker/Buildkit in a reproducible
        way.
        """
        return Docker()


def canonical_json(o):
    """
    Dumps an object as canonical JSON string.

    Canonical JSON does not contain an space (except in strings) and
    have all the keys sorted.

    Args:
        o: The object to dump.

    Return:
        The canonical JSON string.
    """
    return json.dumps(o, sort_keys=True)


class CnabDescriptor:
    """
    Operations on a CNAB descriptor.
    """

    def __init__(self, path):
        """
        Args:
            path: Path to the CNAB descriptor.
        """
        self.path = path

    def archive_to_docker_tarball(self, output_tarball_path):
        """
        Archives to a Docker tarball, using "docker save", all the
        images (both simple images and invocation images) that are given
        in the CNAB descriptor.

        Args:
            output_tarball_path: Path to the output tarball.
        """

        images = self.list_imgrefs_in_bundle()
        print(f"The following images will be saved to {output_tarball_path}:")
        for image in images:
            print(f"    {image}")

        args = [
            'docker',
            'save',
            '--output',
            output_tarball_path,
        ] + images

        start = time.time()
        subprocess.run(args, check=True)
        end = time.time()

        delta = datetime.timedelta(seconds=end - start)
        print(f'{len(images)} images exported in {delta}')

    def list_imgrefs_in_bundle(self):
        """
        Lists all the image references, both of images and invocations images,
        that are given in the CNAB descriptor.
        :param bundle_path:
        :return:
        """
        with open(self.path, 'r') as f:
            descriptor = json.load(f)

        images = []
        for image_name in descriptor.get('images', {}):
            image = descriptor['images'][image_name].get('image', 'image_name')
            images += [image]

        for image in descriptor.get('invocationImages', []):
            images += [image['image']]

        return images


class CLI:
    """
    Command-Line Interface.
    """

    def __init__(self):
        parser = argparse.ArgumentParser(
            description='Make', usage="make <command> [<args>]")
        subcommands = [
            attr for attr in dir(self)
            if not attr.startswith("_") and callable(getattr(self, attr))
        ]
        parser.add_argument(
            'command',
            help='Subcommand to run: one of: ' + " ".join(subcommands))
        args = parser.parse_args(sys.argv[1:2])
        if not hasattr(self, args.command):
            print('Unrecognized command')
            parser.print_help()
            exit(1)
        getattr(self, args.command)()

    def build(self):
        parser = argparse.ArgumentParser(description='Build a CNAB bundle')
        parser.add_argument('path', help='Path to the duffle context')
        parser.add_argument(
            '-o',
            '--output-file',
            help='Path to the output bundle.json file (the ' +
            'CNAB descriptor)',
            required=True)
        args = parser.parse_args(sys.argv[2:])
        DuffleContext(args.path).build_cnab_app(args.output_file)


if __name__ == "__main__":
    try:
        CLI()
    except KeyboardInterrupt as e:
        print("Interrupted")
        sys.exit(1)
