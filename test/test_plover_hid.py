import importlib
import sys
import types

import pytest

MODULE = "plover.machine.plover_hid"


def fake_hid_module(name):
    module = types.ModuleType(name)
    module.device = type("device", (), {})
    module.enumerate = lambda *args, **kwargs: []
    return module


@pytest.fixture
def reload_plover_hid(monkeypatch):
    """Import `plover.machine.plover_hid` with fake `hid`/`hidraw` modules."""

    def reload(*, hidraw=True):
        monkeypatch.setitem(sys.modules, "hid", fake_hid_module("hid"))
        # `None` makes the import machinery raise ImportError.
        monkeypatch.setitem(
            sys.modules, "hidraw", fake_hid_module("hidraw") if hidraw else None
        )
        monkeypatch.delitem(sys.modules, MODULE, raising=False)
        return importlib.import_module(MODULE)

    yield reload
    # Don't leave a module bound to fake backends around for other tests.
    sys.modules.pop(MODULE, None)


def test_prefers_hidraw_backend(reload_plover_hid):
    module = reload_plover_hid()
    assert module.hid.__name__ == "hidraw"


def test_falls_back_to_hid_without_hidraw(reload_plover_hid):
    module = reload_plover_hid(hidraw=False)
    assert module.hid.__name__ == "hid"
