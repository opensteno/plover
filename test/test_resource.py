import inspect
from pathlib import Path

import pytest

from plover.misc import normalize_path
from plover.resource import (
    resource_exists,
    resource_filename,
    resource_timestamp,
    resource_update,
)


@pytest.mark.parametrize(
    "resource, exists, filename",
    (
        # Relative filename.
        (Path(__file__).relative_to(Path.cwd()), True, None),
        # Relative directory.
        (Path(__file__).parent.relative_to(Path.cwd()), True, None),
        # Absolute filename.
        (__file__, True, None),
        # Absolute directory.
        (Path(__file__).parent, True, None),
        # Missing relative path.
        ("test/pouet", False, None),
        # Missing absolute path.
        (Path.cwd() / "test" / "pouet", False, None),
        # Asset filename.
        ("asset:plover:assets/user.json", True, "plover/assets/user.json"),
        # Asset directory.
        ("asset:plover:", True, "plover"),
        ("asset:plover:assets", True, "plover/assets"),
        # Missing asset.
        ("asset:plover:assets/pouet.json", False, "plover/assets/pouet.json"),
        # Invalid asset: missing package and path.
        ("asset:", ValueError, ValueError),
        # Invalid asset: missing path.
        ("asset:package", ValueError, ValueError),
        # Invalid asset: absolute resource path.
        ("asset:plover:/assets/user.json", ValueError, ValueError),
    ),
)
def test_resource(resource, exists, filename):
    resource = str(resource)
    if inspect.isclass(exists):
        exception = exists
        with pytest.raises(exception):
            resource_exists(resource)
        with pytest.raises(exception):
            resource_filename(resource)
        with pytest.raises(exception):
            resource_timestamp(resource)
        return
    assert resource_exists(resource) == exists
    if filename is None:
        filename = resource
    assert normalize_path(resource_filename(resource)) == normalize_path(filename)
    if exists:
        timestamp = Path(filename).stat().st_mtime
        assert resource_timestamp(resource) == timestamp
    else:
        with pytest.raises(FileNotFoundError):
            resource_timestamp(resource)


def test_resource_update(tmp_path):
    # Can't update assets.
    resource = "asset:plover:assets/pouet.json"
    resource_path = Path(resource_filename(resource))
    with pytest.raises(ValueError), resource_update(resource):
        resource_path.write_bytes(b"contents")
    assert not resource_path.exists()
    # Don't update resource on exception (but still cleanup).
    resource = (tmp_path / "resource").resolve()
    exception_str = "Houston, we have a problem"
    with (
        pytest.raises(Exception, match=exception_str),
        resource_update(str(resource)) as tmpf,
    ):
        tmpf = Path(tmpf)
        tmpf.write_bytes(b"contents")
        raise RuntimeError(exception_str)
    assert not resource.exists()
    assert not tmpf.exists()
    # Normal use.
    with resource_update(str(resource)) as tmpf:
        tmpf = Path(tmpf).resolve()
        # Temporary filename must be different.
        assert tmpf != resource
        # And must be empty.
        assert not tmpf.stat().st_size
        # Temporary file must be created in the same
        # directory as the target resource (so an
        # atomic rename can be used).
        assert tmpf.parent == resource.parent
        # Save something.
        tmpf.write_bytes(b"contents")
        st = tmpf.stat()
    assert resource.stat() == st
    assert resource.read_bytes() == b"contents"
