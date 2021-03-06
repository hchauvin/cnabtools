# SPDX-License-Identifier: MIT
# Copyright (c) 2020 Hadrien Chauvin
"""
Interacts with the Duffle native CLI.
"""

import os
import subprocess
import shutil
import urllib.request
import platform

#: Version of DUFFLE to download.
DUFFLE_VERSION = '0.3.5-beta.1'

#: URLs to the Duffle native binaries.
DUFFLE_BINARY_URLS = {
    'Darwin':
        f'https://github.com/cnabio/duffle/releases/download/{DUFFLE_VERSION}/duffle-darwin-amd64',
    'Linux':
        f'https://github.com/cnabio/duffle/releases/download/{DUFFLE_VERSION}/duffle-linux-amd64',
    'Windows':
        f'https://github.com/cnabio/duffle/releases/download/{DUFFLE_VERSION}/duffle-windows-amd64.exe',
}


class Duffle:
    """
    Wraps the Duffle native CLI.

    If the Duffle native CLI is not installed globally, it is downloaded
    within the bundle folder.
    """

    def __init__(self, bundle_path, driver_path, force_local):
        """
        Args:
            bundle_path: The path to the CNAB thick bundle.
            driver_path: The path to the CNAB drivers to put in the PATH
                so that they can be discovered by Duffle.
            force_local: Force downloading the CLI within the bundle folder,
                even if the CLI is already installed globally.
        """
        self.bundle_path = bundle_path
        self.driver_path = driver_path

        if force_local:
            self._ensure_local_duffle()
        else:
            self.duffle_path = shutil.which("duffle")
            if not self.duffle_path:
                self._ensure_local_duffle()

        if not os.path.exists(os.path.expanduser("~/.duffle")):
            self.exec(['init'])

    def exec(self, args):
        subprocess.run(
            [self.duffle_path, '--verbose'] + args,
            env={
                **os.environ, "PATH":
                    self.driver_path + os.pathsep + os.environ.get("PATH", "")
            },
            check=True)

    def _ensure_local_duffle(self):
        p = platform.system()
        self.duffle_path = os.path.join(
            self.bundle_path,
            'bin/duffle.exe' if p == 'Windows' else 'bin/duffle')
        if not os.path.exists(self.duffle_path):
            self._install_duffle()

    def _install_duffle(self):
        p = platform.system()
        url = DUFFLE_BINARY_URLS.get(p)
        if not url:
            raise Exception(f'no duffle binary found for platform {p}')
        print(f"Downloading Duffle from {url}...")
        print("(Duffle is used to interact with the CNAB app)")
        os.makedirs(os.path.join(self.bundle_path, 'bin'))
        urllib.request.urlretrieve(url, self.duffle_path)
        if p == 'Linux' or p == 'Darwin':
            subprocess.run(['chmod', '+x', self.duffle_path])
        print(f"Duffle has successfully been downloaded to {self.duffle_path}")
