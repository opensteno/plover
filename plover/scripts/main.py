# -*- coding: utf-8 -*-
# Copyright (c) 2013 Hesky Fisher
# See LICENSE.txt for details.

"Launch the plover application."

import argparse
import atexit
import os
import sys
import subprocess
import traceback

from importlib.metadata import entry_points

from plover.config import Config
from plover.oslayer.controller import Controller
from plover.oslayer.config import CONFIG_DIR, CONFIG_FILE, PLATFORM
from plover.registry import registry
from plover import log
from plover import __name__ as __software_name__
from plover import __version__


def init_config_dir():
    """Creates plover's config dir.

    This usually only does anything the first time plover is launched.
    """
    # Create the configuration directory if needed.
    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR)

    # Create a default configuration file if one doesn't already exist.
    if not os.path.exists(CONFIG_FILE):
        open(CONFIG_FILE, "wb").close()


def main():
    """Launch plover."""
    description = "Run the plover stenotype engine. This is a graphical application."
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--version",
        action="version",
        version="%s %s" % (__software_name__.capitalize(), __version__),
    )
    parser.add_argument(
        "-s",
        "--script",
        default=None,
        nargs=argparse.REMAINDER,
        help="use another plugin console script as main entrypoint, "
        "passing in the rest of the command line arguments, "
        "print list of available scripts when no argument is given",
    )
    parser.add_argument(
        "-l",
        "--log-level",
        choices=["debug", "info", "warning", "error"],
        default=None,
        help="set log level",
    )
    parser.add_argument("-g", "--gui", default=None, help="set gui")
    args = parser.parse_args(args=sys.argv[1:])
    if args.log_level is not None:
        log.set_level(args.log_level.upper())
    log.setup_platform_handler()

    log.info("Plover %s", __version__)
    log.info("configuration directory: %s", CONFIG_DIR)

    registry.update()

    if args.gui is None:
        gui_priority = {
            "qt": 1,
            "none": -1,
        }
        gui_list = sorted(
            registry.list_plugins("gui"),
            reverse=True,
            key=lambda gui: gui_priority.get(gui.name, 0),
        )
        gui = gui_list[0].obj
    else:
        gui = registry.get_plugin("gui", args.gui).obj

    try:
        if args.script is not None:
            if args.script:
                # Create a mapping of available console scripts,
                # with the following priorities (highest first):
                # - {project_name}-{version}:{script_name}
                # - {project_name}:{script_name}
                # - {script_name}
                console_scripts = {}
                for e in sorted(
                    entry_points(group="console_scripts"),
                    key=lambda e: (e.dist.name, e.name),
                ):
                    for key in (
                        f"{e.dist.name}-{e.dist.version}:{e.name}",
                        f"{e.dist.name}:{e.name}",
                        e.name,
                    ):
                        console_scripts[key] = e
                entrypoint = console_scripts.get(args.script[0])
                if entrypoint is None:
                    log.error("no such script: %s", args.script[0])
                    code = 1
                else:
                    sys.argv = args.script
                    try:
                        code = entrypoint.load()()
                    except SystemExit as e:
                        code = e.code
                    if code is None:
                        code = 0
                    elif not isinstance(code, int):  # sys.exit() also takes a string
                        log.error(code)
                        code = 1
            else:
                print("available script(s):")
                dist = None
                for e in sorted(
                    entry_points(group="console_scripts"),
                    key=lambda e: (e.dist.name, e.name),
                ):
                    if dist != e.dist:
                        dist = e.dist
                        print(f"{dist.name}-{dist.version}:")
                    print(f"- {e.name}")
                code = 0
            os._exit(code)

        # Ensure only one instance of Plover is running at a time.
        with Controller() as controller:
            if controller.is_owner:
                # No other instance, regular startup.
                if PLATFORM == "mac":
                    import appnope

                    appnope.nope()
                init_config_dir()
                # This must be done after calling init_config_dir, so
                # Plover's configuration directory actually exists.
                log.setup_logfile()
                config = Config(CONFIG_FILE)
                code = gui.main(config, controller)
            else:
                log.info("another instance is running, sending `focus` command")
                # Other instance? Try focusing the main window.
                try:
                    controller.send_command("focus")
                except (ConnectionRefusedError, ConnectionResetError):
                    log.error(
                        "connection to existing instance failed, "
                        "force cleaning before restart"
                    )
                    # Assume the previous instance died, leaving
                    # a stray socket, try cleaning it...
                    if not controller.force_cleanup():
                        raise
                    # ...and restart.
                    code = -1
                else:
                    code = 0
    except Exception:
        gui.show_error("Unexpected error", traceback.format_exc())
        code = 2
    # Execute atexit handlers.
    atexit._run_exitfuncs()
    if code == -1:
        # Restart.
        args = sys.argv[:]
        if args[0].endswith(".py") or args[0].endswith(".pyc"):
            # We're running from source.
            spec = sys.modules["__main__"].__spec__
            assert sys.argv[0] == spec.origin
            args[0:1] = [sys.executable, "-m", spec.name]
        if PLATFORM == "win":
            # Workaround https://bugs.python.org/issue19066
            subprocess.Popen(args, cwd=os.getcwd())
            code = 0
        else:
            os.execv(args[0], args)
    os._exit(code)


if __name__ == "__main__":
    main()
