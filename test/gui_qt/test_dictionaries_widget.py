from collections import namedtuple
from pathlib import Path
from textwrap import dedent
from types import SimpleNamespace
import operator

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, Qt

import pytest

from plover.config import DictionaryConfig
from plover.engine import ErroredDictionary
from plover.gui_qt.dictionaries_widget import DictionariesModel, DictionariesWidget
from plover.steno_dictionary import StenoDictionary, StenoDictionaryCollection
from plover.misc import expand_path

from plover_build_utils.testing import parametrize

from unittest import mock

INVALID_EXCEPTION = Exception("loading error")

ICON_TO_CHAR = {
    "error": "!",
    "favorite": "★",
    "loading": "🗘",
    "normal": "⎕",
    "readonly": "🛇",
}
ICON_FROM_CHAR = {c: i for i, c in ICON_TO_CHAR.items()}

ENABLED_TO_CHAR = {
    False: "☐",
    True: "☑",
}
ENABLED_FROM_CHAR = {c: e for e, c in ENABLED_TO_CHAR.items()}

# TODO what does it mean that the MODEL_ROLES are now empty?
MODEL_ROLES = []
# before PySide6 refactoring:
# MODEL_ROLES = sorted([Qt.ItemDataRole.AccessibleTextRole, Qt.ItemDataRole.CheckStateRole,
#                      Qt.ItemDataRole.DecorationRole, Qt.ItemDataRole.DisplayRole,
#                      Qt.ItemDataRole.ToolTipRole])


def parse_state(state_str):
    state_str = dedent(state_str).strip()
    if not state_str:
        return
    for line in state_str.split("\n"):
        enabled, icon, path = line.split()
        yield ENABLED_FROM_CHAR[enabled], ICON_FROM_CHAR[icon], path


def config_dictionaries_from_state(state_str):
    return [
        DictionaryConfig(path, enabled)
        for enabled, icon, path in parse_state(state_str)
    ]


def steno_dictionaries_from_state(state_str, existing_dictionaries=None):
    new_dictionaries = []
    for enabled, icon, path in parse_state(state_str):
        if icon == "loading":
            continue
        path = expand_path(path)
        if existing_dictionaries is None:
            steno_dict = None
        else:
            steno_dict = existing_dictionaries.get(path)
        if steno_dict is None:
            if icon == "error" or path.endswith(".bad"):
                steno_dict = ErroredDictionary(path, INVALID_EXCEPTION)
            else:
                steno_dict = StenoDictionary()
                steno_dict.path = path
                steno_dict.readonly = (
                    icon == "readonly"
                    or path.endswith(".ro")
                    or path.startswith("asset:")
                )
            steno_dict.enabled = enabled
        new_dictionaries.append(steno_dict)
    return new_dictionaries


class ModelTest(
    namedtuple(
        "ModelTest",
        """
                           config dictionaries engine
                           model signals connections
                           initial_state
                           """,
    )
):
    def configure(self, **kwargs):
        self.connections["config_changed"](kwargs)

    def configure_dictionaries(self, state):
        self.configure(dictionaries=config_dictionaries_from_state(state))

    def load_dictionaries(self, state):
        self.dictionaries.set_dicts(
            steno_dictionaries_from_state(state, self.dictionaries)
        )
        self.connections["dictionaries_loaded"](self.dictionaries)
        [
            row
            for row, (enabled, icon, path) in enumerate(parse_state(state))
            if icon != "loading"
        ]

    def check(
        self,
        expected,
        config_change=None,
        data_change=None,
        layout_change=False,
        undo_change=None,
    ):
        __tracebackhide__ = operator.methodcaller("errisinstance", AssertionError)
        expected = dedent(expected).strip()
        if expected:
            expected_config = expected
            expected_state = expected.split("\n")
        else:
            expected_config = ""
            expected_state = []
        actual_state = []
        for row in range(self.model.rowCount()):
            index = self.model.index(row)
            check_state = index.data(Qt.ItemDataRole.CheckStateRole)
            is_checked = check_state == Qt.CheckState.Checked
            icon = index.data(Qt.ItemDataRole.DecorationRole)
            path = index.data(Qt.ItemDataRole.DisplayRole)
            actual_state.append(
                "%s %s %s"
                % (
                    ENABLED_TO_CHAR.get(is_checked, "?"),
                    ICON_TO_CHAR.get(icon, "?"),
                    path,
                )
            )
        assert actual_state == expected_state
        assert not self.engine.mock_calls, "unexpected engine call"
        if config_change == "reload":
            assert self.config.mock_calls == [mock.call({})]
            self.config.reset_mock()
        elif config_change == "update":
            config_update = {
                "dictionaries": config_dictionaries_from_state(expected_config),
            }
            assert self.config.mock_calls == [mock.call(config_update)]
            self.config.reset_mock()
        else:
            assert not self.config.mock_calls, "unexpected config call"
        signal_calls = self.signals.mock_calls[:]
        if undo_change is not None:
            call = signal_calls.pop(0)
            assert call == mock.call.has_undo_changed(undo_change)
        if data_change is not None:
            for row in data_change:
                index = self.model.index(row)
                call = signal_calls.pop(0)
                call.args[2].sort()
                assert call == mock.call.dataChanged(index, index, MODEL_ROLES)
        if layout_change:
            assert signal_calls[0:2] == [
                mock.call.layoutAboutToBeChanged(),
                mock.call.layoutChanged(),
            ]
            del signal_calls[0:2]
        assert not signal_calls
        self.signals.reset_mock()

    def reset_mocks(self):
        self.config.reset_mock()
        self.engine.reset_mock()
        self.signals.reset_mock()


@pytest.fixture
def model_test(monkeypatch, request):
    state = request.function.__doc__
    # Patch configuration directory.
    current_dir = Path(".").resolve()
    monkeypatch.setattr("plover.misc.CONFIG_DIR", str(current_dir))
    monkeypatch.setattr(
        "plover.gui_qt.dictionaries_widget.CONFIG_DIR", str(current_dir)
    )
    # Disable i18n support.
    monkeypatch.setattr("plover.gui_qt.dictionaries_widget._", lambda s: s)
    # Fake config.
    config = mock.PropertyMock()
    config.return_value = {}
    # Dictionaries.
    dictionaries = StenoDictionaryCollection()
    # Fake engine.
    engine = mock.MagicMock(
        spec="""
                            __enter__ __exit__
                            config signal_connect
                            """.split()
    )
    engine.__enter__.return_value = engine
    type(engine).config = config
    signals = mock.MagicMock()
    config.return_value = {
        "dictionaries": config_dictionaries_from_state(state) if state else [],
        "classic_dictionaries_display_order": False,
    }
    # Setup model.
    model = DictionariesModel(engine, {name: name for name in ICON_TO_CHAR}, max_undo=5)
    for slot in """
    dataChanged
    layoutAboutToBeChanged
    layoutChanged
    has_undo_changed
    """.split():
        getattr(model, slot).connect(getattr(signals, slot))
    connections = dict(call.args for call in engine.signal_connect.mock_calls)
    assert connections.keys() == {
        "config_changed",
        "dictionaries_loaded",
        "dictionary_state_changed",
    }
    config.reset_mock()
    engine.reset_mock()
    # Test helper.
    test = ModelTest(config, dictionaries, engine, model, signals, connections, state)
    if state and any(icon != "loading" for enabled, icon, path in parse_state(state)):
        test.load_dictionaries(state)
        test.reset_mocks()
    return test


def test_model_accessible_text_1(model_test):
    """
    ☑ 🗘 read-only.ro
    ☑ 🗘 user.json
    ☑ 🗘 invalid.bad
    ☑ 🗘 commands.json
    ☐ 🗘 asset:plover:assets/main.json
    """
    for n, expected in enumerate(
        (
            "read-only.ro, loading",
            "user.json, loading",
            "invalid.bad, loading",
            "commands.json, loading",
            "asset:plover:assets/main.json, disabled, loading",
        )
    ):
        assert (
            model_test.model.index(n).data(Qt.ItemDataRole.AccessibleTextRole)
            == expected
        )


def test_model_accessible_text_2(model_test):
    """
    ☑ 🛇 read-only.ro
    ☑ ★ user.json
    ☑ ⎕ commands.json
    ☐ 🛇 asset:plover:assets/main.json
    """
    for n, expected in enumerate(
        (
            "read-only.ro, read-only",
            "user.json, favorite",
            "commands.json",
            "asset:plover:assets/main.json, disabled, read-only",
        )
    ):
        assert (
            model_test.model.index(n).data(Qt.ItemDataRole.AccessibleTextRole)
            == expected
        )


def test_model_accessible_text_3(model_test):
    """
    ☑ ! invalid.bad
    """
    expected = "invalid.bad, errored: %s." % INVALID_EXCEPTION
    assert (
        model_test.model.index(0).data(Qt.ItemDataRole.AccessibleTextRole) == expected
    )


def test_model_accessible_text_4(model_test):
    """
    ☐ ! invalid.bad
    """
    expected = "invalid.bad, disabled, errored: %s." % INVALID_EXCEPTION
    assert (
        model_test.model.index(0).data(Qt.ItemDataRole.AccessibleTextRole) == expected
    )


def test_model_add_existing(model_test):
    """
    ☑ ★ user.json
    ☑ ⎕ commands.json
    ☐ ⎕ main.json
    """
    model_test.model.add([expand_path("main.json")])
    model_test.check(model_test.initial_state, config_change="reload")


def test_model_add_new_1(model_test):
    """
    ☑ ★ user.json
    ☐ ⎕ commands.json
    ☑ 🗘 main.json
    """
    model_test.model.add([expand_path("read-only.ro")])
    model_test.check(
        """
        ☑ 🗘 read-only.ro
        ☑ ★ user.json
        ☐ ⎕ commands.json
        ☑ 🗘 main.json
        """,
        config_change="update",
        layout_change=True,
        undo_change=True,
    )


def test_model_add_new_2(model_test):
    """
    ☑ ★ user.json
    ☐ ⎕ commands.json
    ☑ 🗘 main.json
    """
    model_test.model.add(["duplicated.json", "unique.json", "duplicated.json"])
    model_test.check(
        """
        ☑ 🗘 duplicated.json
        ☑ 🗘 unique.json
        ☑ ★ user.json
        ☐ ⎕ commands.json
        ☑ 🗘 main.json
        """,
        config_change="update",
        layout_change=True,
        undo_change=True,
    )


def test_model_add_nothing(model_test):
    """
    ☑ ★ user.json
    ☑ ⎕ commands.json
    ☑ ⎕ main.json
    """
    model_test.model.add([])
    model_test.check(model_test.initial_state)


def test_model_config_update(model_test):
    """
    ☐ ⎕ user.json
    ☑ ★ commands.json
    ☑ 🛇 read-only.ro
    ☑ ! invalid.bad
    ☐ 🛇 asset:plover:assets/main.json
    """
    state = """
    ☑ ★ user.json
    ☐ ⎕ commands.json
    ☑ 🗘 main.json
    """
    model_test.configure_dictionaries(state)
    model_test.check(state, layout_change=True)
    state = """
    ☑ ★ user.json
    ☐ ⎕ commands.json
    ☑ ⎕ main.json
    """
    model_test.load_dictionaries(state)
    model_test.check(state, data_change=[2])


def test_model_insert_1(model_test):
    """
    ☐ ⎕ user.json
    ☑ ★ commands.json
    ☑ 🛇 read-only.ro
    ☑ ! invalid.bad
    ☐ 🛇 asset:plover:assets/main.json
    """
    model_test.model.insert(
        model_test.model.index(2), ["main.json", "commands.json", "read-only.ro"]
    )
    model_test.check(
        """
        ☐ ⎕ user.json
        ☑ 🗘 main.json
        ☑ ★ commands.json
        ☑ 🛇 read-only.ro
        ☑ ! invalid.bad
        ☐ 🛇 asset:plover:assets/main.json
        """,
        config_change="update",
        layout_change=True,
        undo_change=True,
    )


def test_model_insert_2(model_test):
    """
    ☐ ⎕ user.json
    ☑ 🗘 main.json
    ☑ ★ commands.json
    ☑ 🛇 read-only.ro
    ☑ ! invalid.bad
    ☐ 🛇 asset:plover:assets/main.json
    """
    model_test.model.insert(
        QModelIndex(), ["commands.json", "user.json", "commands.json"]
    )
    model_test.check(
        """
        ☑ 🗘 main.json
        ☑ 🛇 read-only.ro
        ☑ ! invalid.bad
        ☐ 🛇 asset:plover:assets/main.json
        ☑ ★ commands.json
        ☐ ⎕ user.json
        """,
        config_change="update",
        layout_change=True,
        undo_change=True,
    )


def test_model_insert_3(model_test):
    """
    ☑ ★ user.json
    ☑ ⎕ commands.json
    ☑ ⎕ main.json
    """
    model_test.model.insert(QModelIndex(), [])
    model_test.check(model_test.initial_state)


def test_model_display_order(model_test):
    """
    ☑ 🛇 read-only.ro
    ☑ ★ user.json
    ☑ ⎕ commands.json
    ☐ 🛇 asset:plover:assets/main.json
    """
    state = model_test.initial_state
    # Flip display order.
    model_test.configure(classic_dictionaries_display_order=True)
    model_test.check("\n".join(reversed(state.split("\n"))), layout_change=True)
    # Reset display order to default.
    model_test.configure(classic_dictionaries_display_order=False)
    model_test.check(state, layout_change=True)


def test_model_favorite(model_test):
    """
    ☑ 🛇 read-only.ro
    ☑ ★ user.json
    ☑ ! invalid.bad
    ☑ ⎕ commands.json
    ☐ 🛇 asset:plover:assets/main.json
    """
    # New favorite.
    model_test.model.setData(
        model_test.model.index(1),
        Qt.CheckState.Unchecked.value,
        Qt.ItemDataRole.CheckStateRole.value,
    )
    model_test.check(
        """
        ☑ 🛇 read-only.ro
        ☐ ⎕ user.json
        ☑ ! invalid.bad
        ☑ ★ commands.json
        ☐ 🛇 asset:plover:assets/main.json
        """,
        config_change="update",
        data_change=[1, 3],
        undo_change=True,
    )
    # No favorite.
    model_test.model.setData(
        model_test.model.index(3),
        Qt.CheckState.Unchecked.value,
        Qt.ItemDataRole.CheckStateRole.value,
    )
    model_test.check(
        """
        ☑ 🛇 read-only.ro
        ☐ ⎕ user.json
        ☑ ! invalid.bad
        ☐ ⎕ commands.json
        ☐ 🛇 asset:plover:assets/main.json
        """,
        config_change="update",
        data_change=[3],
    )


def test_model_initial_setup(model_test):
    """
    ☑ 🗘 read-only.ro
    ☑ 🗘 user.json
    ☑ 🗘 invalid.bad
    ☑ 🗘 commands.json
    ☐ 🗘 asset:plover:assets/main.json
    """
    state = model_test.initial_state
    # Initial state.
    model_test.check(state)
    # First config notification: no-op.
    model_test.configure(**model_test.config.return_value)
    model_test.check(state)
    # After loading dictionaries.
    state = """
    ☑ 🛇 read-only.ro
    ☑ ★ user.json
    ☑ ! invalid.bad
    ☑ ⎕ commands.json
    ☐ 🛇 asset:plover:assets/main.json
    """
    model_test.load_dictionaries(state)
    model_test.check(state, data_change=range(5))


def test_model_iter_loaded(model_test):
    """
    ☑ 🗘 magnum.json
    ☑ ★ user.json
    ☐ ⎕ commands.json
    ☑ 🗘 main.json
    """
    model_test.check(model_test.initial_state)
    index_list = [model_test.model.index(n) for n in range(4)]
    index_list.append(QModelIndex())
    assert (
        list(model_test.model.iter_loaded(index_list)) == model_test.dictionaries.dicts
    )
    assert (
        list(model_test.model.iter_loaded(reversed(index_list)))
        == model_test.dictionaries.dicts
    )
    model_test.configure(classic_dictionaries_display_order=False)
    assert (
        list(model_test.model.iter_loaded(index_list)) == model_test.dictionaries.dicts
    )
    assert (
        list(model_test.model.iter_loaded(reversed(index_list)))
        == model_test.dictionaries.dicts
    )


def test_model_move_dictionaries(model_test):
    """
    ☑ 🛇 read-only.ro
    ☐ ⎕ commands.json
    ☑ ★ user.json
    ☑ ⎕ main.json
    """
    model_test.check(model_test.initial_state)
    model_test.model.move(
        QModelIndex(), [model_test.model.index(0), model_test.model.index(2)]
    )
    model_test.check(
        """
        ☐ ⎕ commands.json
        ☑ ★ main.json
        ☑ 🛇 read-only.ro
        ☑ ⎕ user.json
        """,
        config_change="update",
        layout_change=True,
        undo_change=True,
    )


def test_model_move_down(model_test):
    """
    ☐ ⎕ commands.json
    ☑ ★ main.json
    ☑ 🛇 read-only.ro
    ☑ ⎕ user.json
    """
    model_test.model.move_down([model_test.model.index(n) for n in [1]])
    model_test.check(
        """
        ☐ ⎕ commands.json
        ☑ 🛇 read-only.ro
        ☑ ★ main.json
        ☑ ⎕ user.json
        """,
        config_change="update",
        layout_change=True,
        undo_change=True,
    )
    model_test.model.move_down([model_test.model.index(n) for n in [0, 2]])
    model_test.check(
        """
        ☑ 🛇 read-only.ro
        ☐ ⎕ commands.json
        ☑ ★ user.json
        ☑ ⎕ main.json
        """,
        config_change="update",
        layout_change=True,
    )
    model_test.model.move_down([model_test.model.index(n) for n in [1]])
    model_test.check(
        """
        ☑ 🛇 read-only.ro
        ☑ ★ user.json
        ☐ ⎕ commands.json
        ☑ ⎕ main.json
        """,
        config_change="update",
        layout_change=True,
    )


def test_model_move_down_nothing(model_test):
    """
    ☑ ★ user.json
    ☑ ⎕ commands.json
    ☑ ⎕ main.json
    """
    model_test.model.move_down([QModelIndex()])
    model_test.check(model_test.initial_state)


def test_model_move_up(model_test):
    """
    ☑ 🛇 read-only.ro
    ☑ ⎕ user.json
    ☐ ⎕ commands.json
    ☑ ★ main.json
    """
    model_test.model.move_up([model_test.model.index(n) for n in [2, 3]])
    model_test.check(
        """
        ☑ 🛇 read-only.ro
        ☐ ⎕ commands.json
        ☑ ★ main.json
        ☑ ⎕ user.json
        """,
        config_change="update",
        layout_change=True,
        undo_change=True,
    )
    model_test.model.move_up([model_test.model.index(n) for n in [1, 2]])
    model_test.check(
        """
        ☐ ⎕ commands.json
        ☑ ★ main.json
        ☑ 🛇 read-only.ro
        ☑ ⎕ user.json
        """,
        config_change="update",
        layout_change=True,
    )


def test_model_move_up_nothing(model_test):
    """
    ☑ ★ user.json
    ☑ ⎕ commands.json
    ☑ ⎕ main.json
    """
    model_test.model.move_up([QModelIndex()])
    model_test.check(model_test.initial_state)


def test_model_persistent_index(model_test):
    """
    ☑ 🛇 read-only.ro
    ☑ ★ user.json
    ☑ ⎕ commands.json
    ☐ 🛇 asset:plover:assets/main.json
    """
    persistent_index = QPersistentModelIndex(model_test.model.index(1))
    assert persistent_index.row() == 1
    assert (
        persistent_index.data(Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Checked
    )
    assert persistent_index.data(Qt.ItemDataRole.DecorationRole) == "favorite"
    assert persistent_index.data(Qt.ItemDataRole.DisplayRole) == "user.json"
    model_test.configure(classic_dictionaries_display_order=True)
    assert persistent_index.row() == 2
    assert (
        persistent_index.data(Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Checked
    )
    assert persistent_index.data(Qt.ItemDataRole.DecorationRole) == "favorite"
    assert persistent_index.data(Qt.ItemDataRole.DisplayRole) == "user.json"
    model_test.model.setData(
        persistent_index,
        Qt.CheckState.Unchecked.value,
        Qt.ItemDataRole.CheckStateRole.value,
    )
    assert persistent_index.row() == 2
    assert (
        persistent_index.data(Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Unchecked
    )
    assert persistent_index.data(Qt.ItemDataRole.DecorationRole) == "normal"
    assert persistent_index.data(Qt.ItemDataRole.DisplayRole) == "user.json"


def test_model_qtmodeltester(model_test, qtmodeltester):
    """
    ☑ 🛇 read-only.ro
    ☑ ★ user.json
    ☑ ⎕ commands.json
    ☐ 🛇 asset:plover:assets/main.json
    """
    qtmodeltester.check(model_test.model)


def test_model_remove(model_test):
    """
    ☐ ⎕ commands.json
    ☑ 🛇 read-only.ro
    ☑ ★ main.json
    ☑ ⎕ user.json
    """
    model_test.model.remove([model_test.model.index(n) for n in [0, 3]])
    model_test.check(
        """
        ☑ 🛇 read-only.ro
        ☑ ★ main.json
        """,
        config_change="update",
        layout_change=True,
        undo_change=True,
    )
    model_test.model.remove([model_test.model.index(n) for n in [0, 1]])
    model_test.check("", config_change="update", layout_change=True)


def test_model_remove_nothing_1(model_test):
    """
    ☐ ⎕ commands.json
    ☑ 🛇 read-only.ro
    ☑ ★ main.json
    ☑ ⎕ user.json
    """
    model_test.model.remove([])
    model_test.check(model_test.initial_state)


def test_model_remove_nothing_2(model_test):
    """
    ☐ ⎕ commands.json
    ☑ 🛇 read-only.ro
    ☑ ★ main.json
    ☑ ⎕ user.json
    """
    model_test.model.remove([QModelIndex()])
    model_test.check(model_test.initial_state)


def test_model_set_checked(model_test):
    on_state = "☑ 🗘 user.json"
    off_state = "☐ 🗘 user.json"
    model_test.model.add(["user.json"])
    model_test.check(
        on_state, config_change="update", layout_change=True, undo_change=True
    )
    first_index = model_test.model.index(0)
    for index, value, ret, state in (
        # Invalid index.
        (QModelIndex(), Qt.CheckState.Unchecked.value, False, on_state),
        # Invalid values.
        (first_index, "pouet", False, on_state),
        (first_index, Qt.CheckState.PartiallyChecked.value, False, on_state),
        # Already checked.
        (first_index, Qt.CheckState.Checked.value, False, on_state),
        # Uncheck.
        (first_index, Qt.CheckState.Unchecked.value, True, off_state),
        # Recheck.
        (first_index, Qt.CheckState.Checked.value, True, on_state),
    ):
        assert (
            model_test.model.setData(index, value, Qt.ItemDataRole.CheckStateRole.value)
            == ret
        )
        model_test.check(
            state,
            config_change="update" if ret else None,
            data_change=[index.row()] if ret else None,
        )


def test_model_unrelated_config_change(model_test):
    """
    ☑ ★ user.json
    ☑ ⎕ commands.json
    ☑ ⎕ main.json
    """
    model_test.configure(start_minimized=True)
    model_test.check(model_test.initial_state)


def test_model_undo_1(model_test):
    """
    ☐ 🗘 1.json
    ☐ 🗘 2.json
    ☐ 🗘 3.json
    ☐ 🗘 4.json
    ☐ 🗘 5.json
    ☐ 🗘 6.json
    """
    # Check max undo size.
    state = dedent(model_test.initial_state).strip()
    state_stack = []
    for n in range(6):
        state_stack.append(state)
        state = state.split("\n")
        state[n] = "☑" + state[n][1:]
        state = "\n".join(state)
        model_test.model.setData(
            model_test.model.index(n),
            Qt.CheckState.Checked.value,
            Qt.ItemDataRole.CheckStateRole.value,
        )
        model_test.check(
            state,
            config_change="update",
            data_change=[n],
            undo_change=(True if n == 0 else None),
        )
    for n in range(5):
        model_test.model.undo()
        model_test.check(
            state_stack.pop(),
            config_change="update",
            layout_change=True,
            undo_change=(False if n == 4 else None),
        )


def test_model_undo_2(model_test):
    """
    ☑ ★ user.json
    ☑ ⎕ commands.json
    ☑ ⎕ main.json
    """
    # Changing display order as no impact on the undo stack.
    model_test.configure(classic_dictionaries_display_order=True)
    model_test.check(
        """
        ☑ ⎕ main.json
        ☑ ⎕ commands.json
        ☑ ★ user.json
        """,
        layout_change=True,
    )


class WidgetTest(
    namedtuple(
        "WidgetTest",
        """
                            registry
                            bot widget
                            file_dialog
                            create_dictionary
                            model_test
                            """,
    )
):
    def select(self, selection):
        sm = self.widget.view.selectionModel()
        for row in selection:
            sm.select(self.model.index(row), sm.SelectionFlag.Select)

    def unselect(self, selection):
        sm = self.widget.view.selectionModel()
        for row in selection:
            sm.select(self.model.index(row), sm.SelectionFlag.Deselect)

    def __getattr__(self, name):
        return getattr(self.model_test, name)


@pytest.fixture
def widget_test(model_test, monkeypatch, qtbot):
    # Fake registry.
    def list_plugins(plugin_type):
        assert plugin_type == "dictionary"
        for name, readonly in (
            ("bad", False),
            ("json", False),
            ("ro", True),
        ):
            obj = SimpleNamespace(readonly=readonly)
            yield SimpleNamespace(name=name, obj=obj)

    registry = mock.MagicMock(spec=["list_plugins"])
    registry.list_plugins.side_effect = list_plugins
    monkeypatch.setattr("plover.gui_qt.dictionaries_widget.registry", registry)
    # Fake file dialog.
    file_dialog = mock.MagicMock(
        spec="""
                                 getOpenFileNames
                                 getSaveFileName
                                 """.split()
    )
    monkeypatch.setattr("plover.gui_qt.dictionaries_widget.QFileDialog", file_dialog)

    # Fake `create_dictionary`.
    def create_dictionary(filename, threaded_save=True):
        pass

    steno_dict = mock.create_autospec(StenoDictionary)
    create_dictionary = mock.create_autospec(create_dictionary, return_value=steno_dict)
    monkeypatch.setattr(
        "plover.gui_qt.dictionaries_widget.create_dictionary", create_dictionary
    )
    # Patch `DictionariesModel` constructor to use our own instance.
    monkeypatch.setattr(
        "plover.gui_qt.dictionaries_widget.DictionariesModel",
        lambda engine, icons: model_test.model,
    )
    widget = DictionariesWidget()
    widget.setup(model_test.engine)
    qtbot.addWidget(widget)
    test = WidgetTest(
        registry, qtbot, widget, file_dialog, create_dictionary, model_test
    )
    return test


@parametrize(
    (
        # No selection.
        lambda: (
            (),
            """
     AddDictionaries
     AddTranslation
     """,
        ),
        # No loaded dictionary selected.
        lambda: (
            [1, 4],
            """
     AddDictionaries
     AddTranslation
     MoveDictionariesDown
     MoveDictionariesUp
     RemoveDictionaries
     """,
        ),
        # At least one loaded dictionary selected.
        lambda: (
            [0, 2],
            """
     AddDictionaries
     AddTranslation
     EditDictionaries
     MoveDictionariesDown
     MoveDictionariesUp
     RemoveDictionaries
     SaveDictionaries
     """,
        ),
        lambda: (
            [1, 3],
            """
     AddDictionaries
     AddTranslation
     EditDictionaries
     MoveDictionariesDown
     MoveDictionariesUp
     RemoveDictionaries
     SaveDictionaries
     """,
        ),
    )
)
def test_widget_selection(widget_test, selection, enabled_actions):
    """
    ☑ ★ favorite.json
    ☑ 🗘 loading.json
    ☑ ⎕ normal.json
    ☑ 🛇 read-only.ro
    ☑ ! invalid.bad
    """
    widget_test.select(selection)
    for action_name in """
    AddDictionaries
    AddTranslation
    EditDictionaries
    MoveDictionariesDown
    MoveDictionariesUp
    RemoveDictionaries
    SaveDictionaries
    Undo
    """.split():
        action = getattr(widget_test.widget, "action_" + action_name)
        enabled = action.isEnabled()
        msg = "%s is %s" % (action_name, "enabled" if enabled else "disabled")
        assert enabled == (action_name in enabled_actions), msg


FILE_PICKER_SAVE_FILTER = "Dictionaries (*.bad *.json);; BAD dictionaries (*.bad);; JSON dictionaries (*.json)"


def test_widget_save_copy_1(widget_test):
    """
    ☑ ★ favorite.json
    ☑ 🗘 loading.json
    ☑ ⎕ normal.json
    ☑ 🛇 read-only.ro
    ☑ ! invalid.bad
    """
    # Setup.
    copy_names = (
        expand_path("favorite_copy.json"),
        "",
        expand_path("read-only_copy.json"),
    )
    widget_test.file_dialog.getSaveFileName.side_effect = [
        [name] for name in copy_names
    ]
    steno_dict_copies = (
        mock.create_autospec(StenoDictionary),
        mock.create_autospec(StenoDictionary),
    )
    widget_test.create_dictionary.side_effect = steno_dict_copies
    # Execution.
    widget_test.select(range(5))
    widget_test.widget.action_CopyDictionaries.trigger()
    # Check.
    assert widget_test.file_dialog.mock_calls == [
        mock.call.getSaveFileName(
            parent=widget_test.widget,
            caption="Save a copy of %s as..." % name,
            dir=expand_path("%s - Copy.json" % Path(name).stem),
            filter=FILE_PICKER_SAVE_FILTER,
        )
        for name in ["favorite.json", "normal.json", "read-only.ro"]
    ]
    assert widget_test.create_dictionary.mock_calls == [
        mock.call(name, threaded_save=False) for name in copy_names if name
    ]
    assert steno_dict_copies[0].mock_calls == [
        mock.call.update(widget_test.dictionaries.dicts[0]),
        mock.call.save(),
    ]
    assert steno_dict_copies[1].mock_calls == [
        mock.call.update(widget_test.dictionaries.dicts[2]),
        mock.call.save(),
    ]


def test_widget_save_merge_1(widget_test):
    """
    ☑ ★ favorite.json
    ☑ 🗘 loading.json
    ☑ ⎕ normal.json
    ☑ 🛇 read-only.ro
    ☑ ! invalid.bad
    """
    # Setup.
    merge_name = "favorite + normal + read-only"
    widget_test.file_dialog.getSaveFileName.return_value = [expand_path("merge.json")]
    # Execution.
    widget_test.select(range(5))
    widget_test.widget.action_MergeDictionaries.trigger()
    # Check.
    assert widget_test.file_dialog.mock_calls == [
        mock.call.getSaveFileName(
            parent=widget_test.widget,
            caption="Merge %s as..." % merge_name,
            dir=expand_path(merge_name + ".json"),
            filter=FILE_PICKER_SAVE_FILTER,
        )
    ]
    assert widget_test.create_dictionary.mock_calls == [
        mock.call(expand_path("merge.json"), threaded_save=False)
    ]
    steno_dict = widget_test.create_dictionary.return_value
    assert steno_dict.mock_calls == [
        mock.call.update(widget_test.dictionaries.dicts[2]),
        mock.call.update(widget_test.dictionaries.dicts[1]),
        mock.call.update(widget_test.dictionaries.dicts[0]),
        mock.call.save(),
    ]


def test_widget_save_merge_2(widget_test):
    """
    ☑ ★ favorite.json
    ☑ 🗘 loading.json
    ☑ ⎕ normal.json
    ☑ 🛇 read-only.ro
    ☑ ! invalid.bad
    """
    # Setup.
    merge_name = "favorite + normal"
    widget_test.file_dialog.getSaveFileName.return_value = [""]
    # Execution.
    widget_test.select([0, 2])
    widget_test.widget.action_MergeDictionaries.trigger()
    # Check.
    assert widget_test.file_dialog.mock_calls == [
        mock.call.getSaveFileName(
            parent=widget_test.widget,
            caption="Merge %s as..." % merge_name,
            dir=expand_path(merge_name + ".json"),
            filter=FILE_PICKER_SAVE_FILTER,
        )
    ]
    assert widget_test.create_dictionary.mock_calls == []
