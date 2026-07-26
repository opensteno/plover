#!/usr/bin/env python3

import os
import sys
import zipfile


def zipdir(directory, compression=zipfile.ZIP_DEFLATED):
    zipname = f"{directory}.zip"
    prefix = os.path.dirname(directory)
    with zipfile.ZipFile(zipname, "w", compression) as zf:
        for dirpath, dirnames, filenames in os.walk(directory):
            for name in filenames:
                src = os.path.join(dirpath, name)
                dst = os.path.relpath(src, prefix)
                zf.write(src, dst)


if __name__ == "__main__":
    directory = sys.argv[1]
    zipdir(directory)
