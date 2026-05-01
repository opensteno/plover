import os
import sys
import subprocess

from plover.oslayer.config import CONFIG_DIR, PLATFORM, PLUGINS_PLATFORM


def main():
    args = sys.argv[:]
    args[0:1] = [sys.executable, "-m", "plover.plugins_manager"]
    os.environ["PYTHONUSERBASE"] = os.path.join(CONFIG_DIR, "plugins", PLUGINS_PLATFORM)
    os.environ["PLOVER_BREAK_SYSTEM_PACKAGES"] = "1"
    if PLATFORM == "win":
        # Workaround https://bugs.python.org/issue19066
        subprocess.Popen(args, cwd=os.getcwd())
        sys.exit(0)
    os.execv(args[0], args)


if __name__ == "__main__":
    main()
