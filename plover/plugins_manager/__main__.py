import os
import subprocess
import site
import sys
import itertools

from plover.plugins_manager import global_registry, local_registry
from plover.plugins_manager.utils import running_under_virtualenv


def pip(args, stdin=None, stdout=None, stderr=None, **kwargs):
    cmd = [
        sys.executable,
        "-m",
        "plover.plugins_manager.pip_wrapper",
        "--disable-pip-version-check",
    ]
    env = dict(os.environ)
    # Make sure user plugins are handled
    # even if user site is not enabled.
    if not running_under_virtualenv() and not site.ENABLE_USER_SITE:
        pypath = env.get("PYTHONPATH")
        if pypath is None:
            pypath = []
        else:
            pypath = pypath.split(os.pathsep)
        pypath.insert(0, site.USER_SITE)
        env["PYTHONPATH"] = os.pathsep.join(pypath)
    command = args.pop(0)
    if command == "check":
        cmd.append("check")
    elif command == "install":
        cmd.extend(
            (
                "install",
                "--upgrade-strategy=only-if-needed",
            )
        )
        if not running_under_virtualenv():
            cmd.append("--user")
            if os.environ.get("PLOVER_BREAK_SYSTEM_PACKAGES"):
                cmd.append("--break-system-packages")
    elif command == "uninstall":
        cmd.append("uninstall")
    elif command == "list":
        cmd.extend(
            (
                "list",
                "--format=columns",
            )
        )
    else:
        raise ValueError("invalid command: %s" % command)
    cmd.extend(args)
    return subprocess.Popen(
        cmd, env=env, stdin=stdin, stdout=stdout, stderr=stderr, **kwargs
    )


def list_plugins(freeze=False):
    installed_plugins = local_registry.list_plugins()
    if freeze:
        available_plugins = {}
    else:
        available_plugins = global_registry.list_plugins()
    for name, installed, available in sorted(
        (name, installed_plugins.get(name, []), available_plugins.get(name, []))
        for name in set(itertools.chain(installed_plugins, available_plugins))
    ):
        latest = available[-1] if available else None
        current = installed[-1] if installed else None
        info = latest or current
        if freeze:
            if current:
                print("%s==%s" % (current.name, current.version))
            continue
        print("%s (%s)  - %s" % (info.name, info.version, info.summary))
        if current:
            print("  INSTALLED: %s" % current.version)
            if latest:
                print("  LATEST:    %s" % latest.version)


def main(args=None):
    if args is None:
        args = sys.argv[1:]
    if not args:
        print("Usage: plover_plugins <command> [args]")
        print("Commands: list_plugins [--freeze], check, install, uninstall, list")
        sys.exit(2)
    if args[0] == "list_plugins":
        assert len(args) <= 2
        if len(args) > 1:
            assert args[1] == "--freeze"
            freeze = True
        else:
            freeze = False
        sys.exit(list_plugins(freeze=freeze))
    proc = pip(args)
    sys.exit(proc.wait())


if __name__ == "__main__":
    main()
