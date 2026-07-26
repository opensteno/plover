#!/usr/bin/env python3

import glob
import os
import shutil
import sys


def trim(directory, patterns_file, verbose=True, dry_run=False):
    if dry_run:
        verbose = True
    # Build list of patterns.
    pattern_list = []
    exclude_list = []
    subdir = directory
    with open(patterns_file) as fp:
        for line in fp:
            line = line.strip()
            # Empty line, ignore.
            if not line:
                continue
            # Comment, ignore.
            if line.startswith("#"):
                continue
            # Sub-directory change.
            if line.startswith(":"):
                subdir = os.path.join(directory, line[1:])
                continue
            # Pattern (relative to current sub-directory).
            if line.startswith("!"):
                exclude_list.append(os.path.join(subdir, line[1:]))
            else:
                pattern_list.append(os.path.join(subdir, line))
    # Create list of files to keep based on exclusion list.
    to_keep = set()
    for pattern in exclude_list:
        to_keep.update(glob.glob(pattern, recursive=True))
    # Trim directory tree.
    for pattern in pattern_list:
        for path in reversed(glob.glob(pattern, recursive=True)):
            if path in to_keep:
                continue
            if verbose:
                print("removing", path)
            if dry_run:
                continue
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.unlink(path)


if __name__ == "__main__":
    directory, patterns_file = sys.argv[1:]
    trim(directory, patterns_file)
