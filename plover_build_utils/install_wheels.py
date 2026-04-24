#!/usr/bin/env python3

import os
import subprocess
import sys


# Default directory for caching wheels.
WHEELS_CACHE = os.path.join(".cache", "wheels")


def _split_opts(text):
    args = text.split()
    assert (len(args) % 2) == 0
    return {name: int(nb_args) for name, nb_args in zip(*([iter(args)] * 2))}


# Allowed `pip install/wheel` options.
_PIP_OPTS = _split_opts(
    # General.
    """
    --isolated 0
    -v 0 --verbose 0
    -q 0 --quiet 0
    --log 1
    --proxy 1
    --retries 1
    --timeout 1
    --exists-action 1
    --trusted-host 1
    --cert 1
    --client-cert 1
    --cache-dir 1
    --no-cache-dir 0
    --disable-pip-version-check 0
    --progress-bar 1
    """
    # Install/Wheel.
    """
    -c 1 --constraint 1
    -r 1 --requirement 1
    --no-deps 0
    --use-pep517 0
    """
    # Package Index.
    """
    -i 1 --index-url 1
    --extra-index-url 1
    --no-index 0
    -f 1 --find-links 1
    --process-dependency-links 0
    """
)

# Allowed `pip wheel` only options (not passed to `pip install`).
_PIP_WHEEL_OPTS = _split_opts(
    """
    --no-binary 1
    --only-binary 1
    """
)

# Allowed `pip install` only options.
_PIP_INSTALL_OPTS = _split_opts(
    """
    -t 1 --target 1
    -U 0 --upgrade 0
    --upgrade-strategy 1
    --force-reinstall 0
    -I 0 --ignore-installed 0
    --user 0
    --root 1
    --prefix 1
    --require-hashes 0
    --no-warn-script-location 0
    """
)


def _pip(args, pip_install=None, verbose=True, no_progress=True):
    if no_progress:
        args.append("--progress-bar=off")
    cmd = [sys.executable]
    if sys.flags.no_site:
        cmd.append("-S")
    if sys.flags.no_user_site:
        cmd.append("-s")
    if sys.flags.ignore_environment:
        cmd.append("-E")
    if pip_install is not None:
        cmd.append(pip_install)
    else:
        cmd.extend(("-m", "pip"))
    cmd.extend(args)
    if verbose:
        print("running", " ".join(cmd), flush=True)
    return subprocess.call(cmd)


def install_wheels(
    args, pip_install=None, verbose=True, no_install=False, no_progress=True
):
    wheels_cache = WHEELS_CACHE
    wheel_args = []
    install_args = []
    while len(args) > 0:
        a = args.pop(0)
        if not a.startswith("-"):
            wheel_args.append(a)
            install_args.append(a)
            continue
        if "=" in a:
            a = a.split("=", 1)
            args.insert(0, a[1])
            a = a[0]
        opt = a
        if opt == "-w":
            wheels_cache = args.pop(0)
            continue
        if opt == "--no-install":
            no_install = True
            continue
        if opt == "--progress-bar":
            if args[0] == "off":
                no_progress = True
                del args[0]
                continue
            no_progress = False
        if opt in _PIP_OPTS:
            nb_args = _PIP_OPTS[opt]
            install_only = False
            wheel_only = False
        elif opt in _PIP_WHEEL_OPTS:
            nb_args = _PIP_WHEEL_OPTS[opt]
            install_only = False
            wheel_only = True
        elif opt in _PIP_INSTALL_OPTS:
            nb_args = _PIP_INSTALL_OPTS[opt]
            install_only = True
            wheel_only = False
        else:
            raise ValueError("unsupported option: %s" % opt)
        a = [opt] + args[:nb_args]
        del args[:nb_args]
        if wheel_only:
            wheel_args.extend(a)
        elif not install_only:
            wheel_args.extend(a)
            install_args.extend(a)
        else:
            install_args.extend(a)
    wheel_args[0:0] = ["wheel", "-f", wheels_cache, "-w", wheels_cache]
    install_args[0:0] = ["install", "--no-index", "--no-cache-dir", "-f", wheels_cache]
    pip_kwargs = dict(pip_install=pip_install, no_progress=no_progress)
    code = _pip(wheel_args, **pip_kwargs)
    if code == 0 and not no_install:
        code = _pip(install_args, **pip_kwargs)
    if code != 0:
        raise Exception("wheels installation failed: pip execution returned %u" % code)


if __name__ == "__main__":
    install_wheels(sys.argv[1:])
