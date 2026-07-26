import os
import tempfile
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def make_dict(tmp_path, contents, extension=None, name=None):
    kwargs = {"dir": str(tmp_path)}
    if name is not None:
        kwargs["prefix"] = name + "_"
    if extension is not None:
        kwargs["suffix"] = "." + extension
    fd, path = tempfile.mkstemp(**kwargs)
    try:
        os.write(fd, contents)
        os.close(fd)
        yield Path(path)
    finally:
        os.unlink(path)
