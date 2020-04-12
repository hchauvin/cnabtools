#!/usr/bin/env python3

"""
Alternative Duffle driver for Docker.
"""

# Spec here:
# https://github.com/cnabio/duffle/blob/c7685eb2fb9593a8fac4da15598ab6854bf05ae5/docs/proposal/202-drivers.md

import sys
import os
import json
import subprocess
import shutil
import atexit


def main(option):
    if option == "--handles":
        # Return a comma-separated list of image types that it can handle
        print("docker")
    elif option == "--help":
        print("Alternative Duffle driver for the local Docker daemon")
    elif not option:
        with open('output.txt', 'w') as f:
            json.dump({"error": False}, f)
        operation = json.load(sys.stdin)
        with open('output.txt', 'w') as f:
            json.dump({"error": "XXX"}, f)
        run(operation)
    else:
        with open('output.txt', 'w') as f:
            json.dump({"error": True}, f)
        print(f"Unexpected option '{option}'", file=sys.stderr)
        sys.exit(1)

class Config:
    def __init__(self, allow_docker_host_access=False):
        self.allow_docker_host_access = allow_docker_host_access

def parse_config(operation):
    custom_extension = operation.get('Bundle', {}).get('custom', {}).get('io.chauvin.docker2', {})
    return Config(
        allow_docker_host_access = custom_extension.get('allow-docker-host-access', False)
    )

def run(operation):
    with open('output.txt', 'w') as f:
        json.dump({"error": "XXX2", "operation": operation}, f)

    config = parse_config(operation)

    volumes = []
    if config.allow_docker_host_access:
        volumes += ['/var/run/docker.sock:/var/run/docker.sock']
    if len(operation['files']) > 0:
        files_to_mount_dir = os.path.abspath("files")
        shutil.rmtree(files_to_mount_dir, ignore_errors=True)
        os.mkdir(files_to_mount_dir)

        def remove_files_to_mount_dir():
            shutil.rmtree(files_to_mount_dir)
        atexit.register(remove_files_to_mount_dir)

        for i, container_path in enumerate(operation['files']):
            local_path = f'{files_to_mount_dir}/{i}'
            with open(local_path, 'w') as f:
                f.write(operation['files'][container_path])
            volumes.append(local_path + ':' + container_path + ':ro')
    if operation['outputs'] and len(operation['outputs']) > 0:
        print("WARNING: 'outputs' is currently a NO-OP")
        # FIXME: Uncomment when Duffle gets the latest version of cnab-go.
        # output_local_dir = os.environ.get("CNAB_OUTPUT_DIR")
        # assert output_local_dir, 'expected CNAB_OUTPUT_DIR to have been set'
        # volumes.append(output_local_dir + ':/cnab/app/outputs')

    args = ['docker', 'run', '--rm']
    if config.allow_docker_host_access:
        args += ['--privileged', '--net', 'host']
    for v in volumes:
        args += ['-v', v]
    for name in operation['environment']:
        args += ['-e', name + '=' + operation['environment'][name]]
    args += [
        operation['image']['image'],
        '/cnab/app/run',
        operation['action'],
    ]

    with open('output.txt', 'w') as f:
        json.dump(args, f)

    subprocess.run(args, check=True, stdout=sys.stderr.buffer, stderr=sys.stderr.buffer)


if __name__ == "__main__":
    try:
        main(
            option=sys.argv[1] if len(sys.argv) >= 2 else None,
        )
    except KeyboardInterrupt as e:
        print("Interrupted", sys.stderr)
        sys.exit(1)