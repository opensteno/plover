# Copyright (c) 2011 Hesky Fisher.
# See LICENSE.txt for details.

"""This package abstracts os details for plover."""

import os

from plover import log

from .config import PLATFORM

PLATFORM_PACKAGE = {
    "bsd": "linux",
    "linux": "linux",
    "mac": "osx",
    "win": "windows",
}


def _add_platform_package_to_path():
    platform_package = PLATFORM_PACKAGE.get(PLATFORM)
    if platform_package is None:
        log.warning(f"No platform-specific oslayer package for: {PLATFORM}")
        return
    __path__.insert(0, os.path.join(__path__[0], platform_package))


_add_platform_package_to_path()
