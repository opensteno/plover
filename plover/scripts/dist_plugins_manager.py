import os
import sys
import subprocess

from plover.oslayer.config import CONFIG_DIR, PLATFORM, PLUGINS_PLATFORM


def main():
    if "--no-user-plugins" in sys.argv[3:]:
        sys.argv.remove("--no-user-plugins")
        sys.argv.insert(1, "-s")
    os.environ["PYTHONUSERBASE"] = os.path.join(CONFIG_DIR, "plugins", PLUGINS_PLATFORM)
    os.environ["PLOVER_BREAK_SYSTEM_PACKAGES"] = "1"
    from plover.plugins_manager.__main__ import main as _main
    _main()


if __name__ == "__main__":
    main()
