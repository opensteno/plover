#!/usr/bin/env python3

import fnmatch
import os
import py_compile
import shutil
import sys


def source_less(directory, excludes=()):
    for dirpath, dirnames, filenames in os.walk(directory):
        if "__pycache__" in dirnames:
            dirnames.remove("__pycache__")
            cache = os.path.join(dirpath, "__pycache__")
            shutil.rmtree(cache)
        for name in filenames:
            if not name.endswith(".py"):
                continue
            py = os.path.join(dirpath, name)
            for pattern in excludes:
                if fnmatch.fnmatch(py, pattern):
                    break
            else:
                pyc = py + "c"
                py_compile.compile(py, cfile=pyc)
                os.unlink(py)


if __name__ == "__main__":
    directory = sys.argv[1]
    excludes = sys.argv[2:]
    source_less(directory, excludes)
