import locale
import os

# Note: highest priority first.
LANG_ENV_VARS = ("LC_ALL", "LC_MESSAGES", "LANG")


def get_system_language():
    try:
        return next(filter(None, map(os.environ.get, LANG_ENV_VARS)))
    except StopIteration:
        return locale.getdefaultlocale()[0]
