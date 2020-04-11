# SPDX-License-Identifier: MIT
# Copyright (c) 2020 Hadrien Chauvin

import subprocess
import json
import platform
import time
import datetime

class Bundler:

    SUPPORTED_PLATFORMS = ['Darwin', 'Linux']

    def check_can_bundle(self):
        p = platform.system()
        if not p in Bundler.SUPPORTED_PLATFORMS:
            raise Exception(
                f"Your platform {p} is not supported by the bundler; supported platforms: " +
                ", ".join(Bundler.SUPPORTED_PLATFORMS))

    def archive_docker(self, bundle_path, output_tarball_path):
        self.check_can_bundle()

        images = self._images(bundle_path)
        print(f"The following images will be saved to {output_tarball_path}:")
        for image in images:
            print(f"    {image}")

        args = [
                   'docker', 'save',
                   '--output', output_tarball_path,
               ] + images

        start = time.time()
        subprocess.run(args, check=True)
        end = time.time()

        delta = datetime.timedelta(seconds=end - start)
        print(f'{len(images)} images exported in {delta}')

    def push_docker(self, bundle_path, output_registry_spec_path):
        pass

    def _images(self, bundle_path):
        with open(bundle_path, 'r') as f:
            cnab = json.load(f)

        images = []
        for image_name in cnab.get('images', {}):
            image = cnab['images'][image_name].get('image', 'image_name')
            images += [image]

        for image in cnab.get('invocationImages', []):
            images += [image['image']]

        return images