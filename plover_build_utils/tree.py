#!/usr/bin/env python3

import functools
import operator
import os.path
import stat
import sys
from pathlib import Path

BLOCK_SIZES = (
    (1024 * 1024 * 1024 * 1024, "T"),
    (1024 * 1024 * 1024, "G"),
    (1024 * 1024, "M"),
    (1024, "K"),
)


def format_size(size):
    for bs, unit in BLOCK_SIZES:
        if size >= bs:
            return f"{size / bs:.1f}{unit}"
    return str(size)


def tree(path, dirs_only=False, max_depth=0, _depth=0):
    path = Path(path)
    lst = path.lstat()
    is_symlink = stat.S_ISLNK(lst.st_mode)
    st = lst if is_symlink else path.stat()
    is_dir = stat.S_ISDIR(st.st_mode)
    if is_symlink:
        size = 0
    elif is_dir:
        size = functools.reduce(
            operator.add,
            [
                tree(p, dirs_only=dirs_only, max_depth=max_depth, _depth=_depth + 1)
                for p in sorted(path.iterdir())
            ],
            0,
        )
    else:
        size = lst.st_size
    if (is_dir or not dirs_only) and (not max_depth or _depth <= max_depth):
        p = str(path)
        if is_dir:
            p += os.path.sep
        if is_symlink:
            p += " -> " + os.readlink(str(path))
        print(f"{format_size(size):>10}  {p}")
    return size


def main():
    args = []
    max_depth = 0
    dirs_only = False
    argv = iter(sys.argv[1:])
    for a in argv:
        if a == "-d":
            dirs_only = True
            continue
        if a == "-L":
            max_depth = int(next(argv))
            continue
        if a.startswith("-"):
            raise ValueError(a)
        args.append(a)
    for a in args:
        tree(a, dirs_only=dirs_only, max_depth=max_depth)


if __name__ == "__main__":
    main()
