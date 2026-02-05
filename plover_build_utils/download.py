#!/usr/bin/env python3

from urllib.request import urlopen
from urllib.parse import urlsplit
import hashlib
import os
import sys


DOWNLOADS_DIR = os.path.join(".cache", "downloads")


def download(url, sha1=None, filename=None, downloads_dir=DOWNLOADS_DIR):
    if filename is None:
        filename = os.path.basename(urlsplit(url).path)
    dst = os.path.join(downloads_dir, filename)
    dst_dir = os.path.dirname(dst)
    if not os.path.exists(dst_dir):
        os.makedirs(dst_dir)
    retries = 0
    while retries < 2:
        if sha1 is None or not os.path.exists(dst):
            retries += 1
            try:
                with urlopen(url) as req, open(dst, "wb") as fp:
                    fp.write(req.read())
            except Exception as e:
                print("error", e, file=sys.stderr)
                continue
        if sha1 is None:
            break
        h = hashlib.sha1()
        with open(dst, "rb") as fp:
            while True:
                d = fp.read(4 * 1024 * 1024)
                if not d:
                    break
                h.update(d)
        if h.hexdigest() == sha1:
            break
        print(
            "sha1 does not match: %s instead of %s" % (h.hexdigest(), sha1),
            file=sys.stderr,
        )
        os.unlink(dst)
    assert os.path.exists(dst), "could not successfully retrieve %s" % url
    return dst


if __name__ == "__main__":
    args = sys.argv[1:]
    url = args.pop(0)
    sha1 = None
    filename = None
    downloads_dir = DOWNLOADS_DIR
    if args:
        sha1 = args.pop(0) or None
    if args:
        filename = args.pop(0) or None
    if args:
        downloads_dir = args.pop(0) or DOWNLOADS_DIR
    print(download(url, sha1, filename, downloads_dir))
