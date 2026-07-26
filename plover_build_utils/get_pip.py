#!/usr/bin/env python3

import os
import subprocess
import sys


def get_pip(args=None):
    os.makedirs("build", exist_ok=True)

    # can be downloaded from https://github.com/pypa/get-pip/tags by following the commit ID and opening the raw file
    cmd = [
        "curl",
        "https://raw.githubusercontent.com/pypa/get-pip/c8048075753de535e6279e501940f41bc040c081/public/get-pip.py",
        "-o",
        "build/get-pip.py",
    ]
    subprocess.call(cmd)
    cmd = [sys.executable, "build/get-pip.py", "pip==25.1"]
    subprocess.call(cmd)
    if args:
        cmd = [sys.executable, "-m", "pip", "install"] + args
        print("running", " ".join(cmd), flush=True)
        subprocess.check_call(cmd)


if __name__ == "__main__":
    get_pip(sys.argv[1:])
