#!/usr/bin/env python3

# SPDX-License-Identifier: MIT
# Copyright (c) 2020 Hadrien Chauvin

# NOTE: This script requires python 3.7 or higher.

import argparse
import os
import subprocess
import sys
import json
from .duffle import Duffle


def install(duffle, skip_load, app_name, bundle_path, set, set_file):
    if not skip_load:
        load_images(bundle_path)
    try:
        os.remove(os.path.expanduser(f'~/.duffle/claims/{app_name}.json'))
    except OSError:
        pass
    args = ['install', '-d', 'docker2',
            app_name, os.path.join(bundle_path, 'bundle.json'),
            '--bundle-is-file']
    for v in set:
        args += ['--set', v]
    for v in set_file:
        args += ['--set-file', v]
    duffle.exec(args)


def run(duffle, app_name, set, set_file):
    args = ['run', '-d', 'docker2', app_name]
    for v in set:
        args += ['--set', v]
    for v in set_file:
        args += ['--set-file', v]
    duffle.exec(args)


def uninstall(duffle, app_name):
    duffle.exec(['uninstall', '-d', 'docker2', app_name])


def load_images(bundle_path):
    if os.path.exists(os.path.join(bundle_path, 'images.tar')):
        print("Load Docker images...")
        subprocess.run(['docker', 'load', '--input', os.path.join(bundle_path, 'images.tar')], check=True)
    elif os.path.exists(os.path.join(bundle_path, 'registry.json')):
        with open(os.path.join(bundle_path, 'registry.json')) as f:
            registry_spec = json.load(f)
        load_images_from_registry(registry_spec)


def load_images_from_registry(registry_spec):
    pass


class Make:
    """
    Command-Line Interface.
    """

    def __init__(self, default_app_name, bundle_path, driver_path):
        self.default_app_name = default_app_name
        self.bundle_path = bundle_path
        self.driver_path = driver_path

        parser = argparse.ArgumentParser(
            description='Make',
            usage="make <command> [<args>]")
        subcommands = [attr for attr in dir(self) if not attr.startswith("_") and callable(getattr(self, attr))]
        parser.add_argument('command',
                            help='Subcommand to run: one of: ' + " ".join(
                                subcommands))
        args = parser.parse_args(sys.argv[1:2])
        if not hasattr(self, args.command):
            print('Unrecognized command')
            parser.print_help()
            exit(1)
        getattr(self, args.command)()

    def install(self):
        parser = argparse.ArgumentParser(
            description='Install the application')
        parser.add_argument('--skip-load', dest='skip_load', action='store_true',
                            help='Skip loading the images')
        parser.add_argument('--name',
                            help='Application name',
                            default=self.default_app_name)
        parser.add_argument('--set',
                            nargs='*',
                            help='Set individual parameters as NAME=VALUE pairs')
        parser.add_argument('--set-file',
                            dest='set_file',
                            nargs='*',
                            help='Set individual parameters from file content as NAME=SOURCE-PATH pairs')
        args = parser.parse_args(sys.argv[2:])
        install(self._duffle(),
                skip_load=args.skip_load,
                app_name=args.name,
                bundle_path=self.bundle_path,
                set=args.set or [],
                set_file=args.set_file or [])

    def run(self):
        parser = argparse.ArgumentParser(
            description='Run an arbitrary CNAB action')
        parser.add_argument('--name',
                            help='Application name',
                            default=self.default_app_name)
        parser.add_argument('--set',
                            nargs='*',
                            help='Set individual parameters as NAME=VALUE pairs')
        parser.add_argument('--set-file',
                            dest='set_file',
                            nargs='*',
                            help='Set individual parameters from file content as NAME=SOURCE-PATH pairs')
        args = parser.parse_args(sys.argv[2:])
        run(self._duffle(),
            app_name=args.name,
            set=args.set or [],
            set_file=args.set_file or [])

    def uninstall(self):
        parser = argparse.ArgumentParser(
            description='Uninstall the application')
        parser.add_argument('--name',
                            help='Application name',
                            default=self.default_app_name)
        args = parser.parse_args(sys.argv[2:])
        uninstall(self._duffle(),
                  app_name=args.name)

    def _duffle(self):
        return Duffle(bundle_path=self.bundle_path, driver_path=self.driver_path,
                      force_local=os.environ.get("FORCE_LOCAL_DUFFLE") == "1")


if __name__ == "__main__":
    try:
        bundle_path = os.path.dirname(os.path.realpath(__file__))
        bundle_name = os.path.basename(bundle_path)
        Make(default_app_name=bundle_name,
             bundle_path=bundle_path,
             driver_path=f'{bundle_path}/cnab-drivers')
    except KeyboardInterrupt as e:
        print("Interrupted")
        sys.exit(1)