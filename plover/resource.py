import os
import shutil
from contextlib import contextmanager
from importlib.util import find_spec
from tempfile import NamedTemporaryFile

ASSET_SCHEME = "asset:"


def _asset_filename(resource_name):
    components = resource_name[len(ASSET_SCHEME) :].split(":", 1)
    if len(components) != 2:
        raise ValueError(f"invalid asset: {resource_name}")
    if os.path.isabs(components[1]):
        raise ValueError(f"invalid asset: {resource_name}")
    # Check for a leading (back)slash since os.path.isabs
    # returns False on Windows if the given path starts with
    # exactly one (back)slash.
    if components[1].startswith(("/", "\\")):
        raise ValueError(f"invalid asset: {resource_name}")
    package_dir = os.path.dirname(find_spec(components[0]).origin)
    return os.path.join(package_dir, components[1])


def resource_exists(resource_name):
    if resource_name.startswith(ASSET_SCHEME):
        resource_name = _asset_filename(resource_name)
    return os.path.exists(resource_name)


def resource_filename(resource_name):
    if resource_name.startswith(ASSET_SCHEME):
        resource_name = _asset_filename(resource_name)
    return resource_name


def resource_timestamp(resource_name):
    filename = resource_filename(resource_name)
    return os.path.getmtime(filename)


@contextmanager
def resource_update(resource_name):
    if resource_name.startswith(ASSET_SCHEME):
        raise ValueError(f"updating an asset is unsupported: {resource_name}")
    filename = resource_filename(resource_name)
    directory = os.path.dirname(filename)
    extension = os.path.splitext(filename)[1]
    # Only used to generate a unique filename: closed right away, removed on error.
    tempfile = NamedTemporaryFile(  # noqa: SIM115
        delete=False, dir=directory, suffix=extension or None
    )
    try:
        tempfile.close()
        yield tempfile.name
        shutil.move(tempfile.name, filename)
    finally:
        if os.path.exists(tempfile.name):
            os.unlink(tempfile.name)
