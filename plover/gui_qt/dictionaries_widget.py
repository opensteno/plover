from contextlib import contextmanager
import os

from PySide6.QtCore import (
    QAbstractListModel,
    QModelIndex,
    Qt,
    Signal,
    Slot,
)
from PySide6.QtGui import (
    QCursor,
    QIcon,
)
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QMenu,
)

from plover import _
from plover.config import DictionaryConfig
from plover.dictionary.base import create_dictionary
from plover.engine import ErroredDictionary
from plover.misc import normalize_path
from plover.oslayer.config import CONFIG_DIR
from plover.registry import registry

from plover.gui_qt.dictionaries_widget_ui import Ui_DictionariesWidget
from plover.gui_qt.dictionary_editor import DictionaryEditor
from plover.gui_qt.utils import ToolBar


def _dictionary_formats(include_readonly=True):
    return {
        plugin.name
        for plugin in registry.list_plugins("dictionary")
        if include_readonly or not plugin.obj.readonly
    }


def _dictionary_filters(include_readonly=True):
    formats = sorted(_dictionary_formats(include_readonly=include_readonly))
    filters = ["*." + ext for ext in formats]
    # i18n: Widget: “DictionariesWidget”, file picker.
    filters = [_("Dictionaries ({extensions})").format(extensions=" ".join(filters))]
    filters.extend(
        # i18n: Widget: “DictionariesWidget”, file picker.
        _("{format} dictionaries ({extensions})").format(
            format=ext.strip(".").upper(),
            extensions="*." + ext,
        )
        for ext in formats
    )
    return ";; ".join(filters)


@contextmanager
def _new_dictionary(filename):
    try:
        d = create_dictionary(filename, threaded_save=False)
        yield d
        d.save()
    except Exception as e:
        raise Exception("creating dictionary %s failed. %s" % (filename, e)) from e


class DictionariesModel(QAbstractListModel):
    class DictionaryItem:
        __slots__ = "row path enabled short_path _loaded state".split()

        def __init__(self, row, config, loaded=None):
            self.row = row
            self.path = config.path
            self.enabled = config.enabled
            self.short_path = config.short_path
            self.loaded = loaded

        @property
        def loaded(self):
            return self._loaded

        @loaded.setter
        def loaded(self, loaded):
            if loaded is None:
                state = "loading"
            elif isinstance(loaded, ErroredDictionary):
                state = "error"
            elif loaded.readonly:
                state = "readonly"
            else:
                state = "normal"
            self.state = state
            self._loaded = loaded

        @property
        def config(self):
            return DictionaryConfig(self.path, self.enabled)

        @property
        def is_loaded(self):
            return self.state not in {"loading", "error"}

    SUPPORTED_ROLES = [
        Qt.ItemDataRole.AccessibleTextRole,
        Qt.ItemDataRole.CheckStateRole,
        Qt.ItemDataRole.DecorationRole,
        Qt.ItemDataRole.DisplayRole,
        Qt.ItemDataRole.ToolTipRole,
    ]

    FLAGS = (
        Qt.ItemFlag.ItemIsEnabled
        | Qt.ItemFlag.ItemIsSelectable
        | Qt.ItemFlag.ItemIsUserCheckable
        | Qt.ItemFlag.ItemIsDragEnabled
    )

    has_undo_changed = Signal(bool)

    def __init__(self, engine, icons, max_undo=20):
        super().__init__()
        self._engine = engine
        self._favorite = None
        self._from_path = {}
        self._from_row = []
        self._reverse_order = False
        self._undo_stack = []
        self._max_undo = max_undo
        self._icons = icons
        with engine:
            config = engine.config
            engine.signal_connect("config_changed", self._on_config_changed)
            engine.signal_connect("dictionaries_loaded", self._on_dictionaries_loaded)
            engine.signal_connect(
                "dictionary_state_changed", self._on_dictionary_state_changed
            )
            self._reset_items(
                config["dictionaries"],
                config["classic_dictionaries_display_order"],
                backup=False,
                publish=False,
            )

    @property
    def _config(self):
        item_list = self._from_row
        if self._reverse_order:
            item_list = reversed(item_list)
        return [item.config for item in item_list]

    def _updated_rows(self, row_list):
        for row in row_list:
            index = self.index(row)
            self.dataChanged.emit(index, index, self.SUPPORTED_ROLES)

    def _backup_config(self):
        config = self._config
        assert not self._undo_stack or config != self._undo_stack[-1]
        self._undo_stack.append(config)
        if len(self._undo_stack) == 1:
            self.has_undo_changed.emit(True)
        elif len(self._undo_stack) > self._max_undo:
            self._undo_stack.pop(0)

    def _publish_config(self, config):
        self._engine.config = {"dictionaries": config}

    def _update_favorite(self):
        item_list = self._from_row
        if self._reverse_order:
            item_list = reversed(item_list)
        old, new = self._favorite, None
        for item in item_list:
            if item.enabled and item.state == "normal":
                new = item
                break
        if new is old:
            return set()
        self._favorite = new
        return {favorite.row for favorite in filter(None, (old, new))}

    def _reset_items(self, config, reverse_order=None, backup=True, publish=True):
        if backup:
            self._backup_config()
        if reverse_order is None:
            reverse_order = self._reverse_order
        self.layoutAboutToBeChanged.emit()
        old_persistent_indexes = self.persistentIndexList()
        assert all(index.isValid() for index in old_persistent_indexes)
        old_persistent_items = [
            self._from_row[index.row()] for index in old_persistent_indexes
        ]
        from_row = []
        from_path = {}
        for row, d in enumerate(reversed(config) if reverse_order else config):
            item = self._from_path.get(d.path)
            if item is None:
                item = self.DictionaryItem(row, d)
            else:
                item.row = row
                item.enabled = d.enabled
            assert d.path not in from_path
            from_path[d.path] = item
            from_row.append(item)
        self._reverse_order = reverse_order
        self._from_path = from_path
        self._from_row = from_row
        self._update_favorite()
        new_persistent_indexes = []
        for old_item in old_persistent_items:
            new_item = self._from_path.get(old_item.path)
            if new_item is None:
                new_index = QModelIndex()
            else:
                new_index = self.index(new_item.row)
            new_persistent_indexes.append(new_index)
        self.changePersistentIndexList(old_persistent_indexes, new_persistent_indexes)
        self.layoutChanged.emit()
        if publish:
            self._publish_config(config)

    def _on_config_changed(self, config_update):
        config = config_update.get("dictionaries")
        reverse_order = config_update.get("classic_dictionaries_display_order")
        noop = True
        if reverse_order is not None:
            noop = reverse_order == self._reverse_order
        if config is not None:
            noop = noop and config == self._config
        if noop:
            return
        if config is None:
            config = self._config
        else:
            if self._undo_stack:
                self.has_undo_changed.emit(False)
            self._undo_stack.clear()
        self._reset_items(config, reverse_order, backup=False, publish=False)

    def _on_dictionaries_loaded(self, loaded_dictionaries):
        updated_rows = set()
        for item in self._from_row:
            loaded = loaded_dictionaries.get(item.path)
            if loaded == item.loaded:
                continue
            item.loaded = loaded
            updated_rows.add(item.row)
        if not updated_rows:
            return
        updated_rows.update(self._update_favorite())
        self._updated_rows(updated_rows)

    def _on_dictionary_state_changed(self, filename, d):
        [item] = [item for item in self._from_row if item.path == filename]
        if item.loaded != d:
            item.loaded = d
            self._updated_rows([item.row])

    def _move(self, index_list, step):
        row_list = sorted(self._normalized_row_list(index_list))
        if not row_list:
            return
        old_path_list = [item.path for item in self._from_row]
        new_path_list = old_path_list[:]
        if step > 0:
            row_list = reversed(row_list)
            row_limit = len(self._from_row) - 1
            update_row = min
        else:
            row_limit = 0
            update_row = max
        for old_row in row_list:
            new_row = update_row(old_row + step, row_limit)
            new_path_list.insert(new_row, new_path_list.pop(old_row))
            row_limit = new_row - step
        if old_path_list == new_path_list:
            return
        if self._reverse_order:
            new_path_list = reversed(new_path_list)
        config = [self._from_path[path].config for path in new_path_list]
        self._reset_items(config)

    @staticmethod
    def _normalized_path_list(path_list):
        return list(dict.fromkeys(map(normalize_path, path_list)))

    @staticmethod
    def _normalized_row_list(index_list):
        return list(
            dict.fromkeys(index.row() for index in index_list if index.isValid())
        )

    def _insert(self, dest_row, path_list):
        old_path_list = [item.path for item in self._from_row]
        new_path_list = (
            [p for p in old_path_list[:dest_row] if p not in path_list]
            + path_list
            + [p for p in old_path_list[dest_row:] if p not in path_list]
        )
        if new_path_list == old_path_list:
            return
        if self._reverse_order:
            new_path_list = reversed(new_path_list)
        config = [
            self._from_path[path].config
            if path in self._from_path
            else DictionaryConfig(path)
            for path in new_path_list
        ]
        self._reset_items(config)

    def add(self, path_list):
        new_path_list = self._normalized_path_list(
            path for path in path_list if path not in self._from_path
        )
        if new_path_list:
            # Add with highest priority.
            if self._reverse_order:
                dest_row = len(self._from_path)
                new_path_list = reversed(new_path_list)
            else:
                dest_row = 0
            self._insert(dest_row, new_path_list)
        elif path_list:
            # Trigger a reload, just in case.
            self._engine.config = {}

    def iter_loaded(self, index_list):
        row_list = sorted(self._normalized_row_list(index_list))
        if self._reverse_order:
            row_list = reversed(row_list)
        for row in row_list:
            item = self._from_row[row]
            if item.is_loaded:
                yield item.loaded

    def insert(self, index, path_list):
        # Insert at the end if `index` is not valid.
        row = index.row() if index.isValid() else len(self._from_row)
        self._insert(row, self._normalized_path_list(path_list))

    def move(self, dst_index, src_index_list):
        self.insert(
            dst_index,
            [
                self._from_row[row].path
                for row in self._normalized_row_list(src_index_list)
            ],
        )

    def move_down(self, index_list):
        self._move(index_list, +1)

    def move_up(self, index_list):
        self._move(index_list, -1)

    def remove(self, index_list):
        row_set = self._normalized_row_list(index_list)
        if not row_set:
            return
        config = [item.config for item in self._from_row if item.row not in row_set]
        self._reset_items(config)

    def undo(self):
        config = self._undo_stack.pop()
        if not self._undo_stack:
            self.has_undo_changed.emit(False)
        self._reset_items(config, backup=False)

    # Model API.

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._from_row)

    def flags(self, index):
        return self.FLAGS if index.isValid() else Qt.ItemFlag.NoItemFlags

    def data(self, index, role):
        if not index.isValid() or role not in self.SUPPORTED_ROLES:
            return None
        d = self._from_row[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return d.short_path
        if role == Qt.ItemDataRole.CheckStateRole:
            return Qt.CheckState.Checked if d.enabled else Qt.CheckState.Unchecked
        if role == Qt.ItemDataRole.AccessibleTextRole:
            accessible_text = [d.short_path]
            if not d.enabled:
                # i18n: Widget: “DictionariesWidget”, accessible text.
                accessible_text.append(_("disabled"))
            if d is self._favorite:
                # i18n: Widget: “DictionariesWidget”, accessible text.
                accessible_text.append(_("favorite"))
            elif d.state == "error":
                # i18n: Widget: “DictionariesWidget”, accessible text.
                accessible_text.append(
                    _("errored: {exception}.").format(exception=str(d.loaded.exception))
                )
            elif d.state == "loading":
                # i18n: Widget: “DictionariesWidget”, accessible text.
                accessible_text.append(_("loading"))
            elif d.state == "readonly":
                # i18n: Widget: “DictionariesWidget”, accessible text.
                accessible_text.append(_("read-only"))
            return ", ".join(accessible_text)
        if role == Qt.ItemDataRole.DecorationRole:
            return self._icons.get("favorite" if d is self._favorite else d.state)
        if role == Qt.ItemDataRole.ToolTipRole:
            # i18n: Widget: “DictionariesWidget”, tooltip.
            tooltip = [_("Full path: {path}.").format(path=d.config.path)]
            if d is self._favorite:
                # i18n: Widget: “DictionariesWidget”, tool tip.
                tooltip.append(_("This dictionary is marked as the favorite."))
            elif d.state == "loading":
                # i18n: Widget: “DictionariesWidget”, tool tip.
                tooltip.append(_("This dictionary is being loaded."))
            elif d.state == "error":
                # i18n: Widget: “DictionariesWidget”, tool tip.
                tooltip.append(
                    _("Loading this dictionary failed: {exception}.").format(
                        exception=str(d.loaded.exception)
                    )
                )
            elif d.state == "readonly":
                # i18n: Widget: “DictionariesWidget”, tool tip.
                tooltip.append(_("This dictionary is read-only."))
            return "\n\n".join(tooltip)
        return None

    def setData(self, index, value, role):
        if not index.isValid() or role != Qt.ItemDataRole.CheckStateRole.value:
            return False
        if value == Qt.CheckState.Checked.value:
            enabled = True
        elif value == Qt.CheckState.Unchecked.value:
            enabled = False
        else:
            return False
        d = self._from_row[index.row()]
        if d.enabled == enabled:
            return False
        self._backup_config()
        d.enabled = enabled
        self._updated_rows({d.row} | self._update_favorite())
        self._publish_config(self._config)
        return True


class DictionariesWidget(QGroupBox, Ui_DictionariesWidget):
    signal_add_translation = Signal(str)

    # TODO what to do with parent?
    def __init__(self, parent=None):
        super().__init__()
        self.setupUi(self)
        self._setup = False
        self._engine = None
        self._model = None
        # The save/open/new dialogs will open on that directory.
        self._file_dialogs_directory = CONFIG_DIR
        # Start with all actions disabled (until `setup` is called).
        for action in (
            self.action_AddDictionaries,
            self.action_AddTranslation,
            self.action_EditDictionaries,
            self.action_MoveDictionariesDown,
            self.action_MoveDictionariesUp,
            self.action_RemoveDictionaries,
            self.action_SaveDictionaries,
            self.action_Undo,
        ):
            action.setEnabled(False)
        # Toolbar.
        self.layout().addWidget(
            ToolBar(
                self.action_Undo,
                None,
                self.action_EditDictionaries,
                self.action_RemoveDictionaries,
                self.action_AddDictionaries,
                self.action_AddTranslation,
                None,
                self.action_MoveDictionariesUp,
                self.action_MoveDictionariesDown,
            )
        )
        # Add menu.
        self.menu_AddDictionaries = QMenu(self.action_AddDictionaries.text())
        self.menu_AddDictionaries.setIcon(self.action_AddDictionaries.icon())
        self.menu_AddDictionaries.addAction(self.action_OpenDictionaries)
        self.menu_AddDictionaries.addAction(self.action_CreateDictionary)
        self.action_AddDictionaries.setMenu(self.menu_AddDictionaries)
        # Save menu.
        self.menu_SaveDictionaries = QMenu(self.action_SaveDictionaries.text())
        self.menu_SaveDictionaries.setIcon(self.action_SaveDictionaries.icon())
        self.menu_SaveDictionaries.addAction(self.action_CopyDictionaries)
        self.menu_SaveDictionaries.addAction(self.action_MergeDictionaries)
        self.view.dragEnterEvent = self._drag_enter_event
        self.view.dragMoveEvent = self._drag_move_event
        self.view.dropEvent = self._drag_drop_event
        self.setFocusProxy(self.view)
        # Edit context menu.
        edit_menu = QMenu()
        edit_menu.addAction(self.action_Undo)
        edit_menu.addSeparator()
        edit_menu.addMenu(self.menu_AddDictionaries)
        edit_menu.addAction(self.action_EditDictionaries)
        edit_menu.addMenu(self.menu_SaveDictionaries)
        edit_menu.addAction(self.action_RemoveDictionaries)
        edit_menu.addSeparator()
        edit_menu.addAction(self.action_MoveDictionariesUp)
        edit_menu.addAction(self.action_MoveDictionariesDown)
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.view.customContextMenuRequested.connect(
            lambda p: edit_menu.exec(self.view.mapToGlobal(p))
        )
        self.edit_menu = edit_menu

    def setup(self, engine):
        assert not self._setup
        self._engine = engine
        self._model = DictionariesModel(
            engine,
            {
                name: QIcon(":resources/dictionary_%s.svg" % name)
                for name in "favorite loading error readonly normal".split()
            },
        )
        self._model.has_undo_changed.connect(self.toggle_undo_action)
        self.view.setModel(self._model)
        self.view.selectionModel().selectionChanged.connect(
            self.handle_selection_change
        )
        for action in (
            self.action_AddDictionaries,
            self.action_AddTranslation,
        ):
            action.setEnabled(True)
        self._setup = True

    @property
    def _selected(self):
        return sorted(self.view.selectedIndexes(), key=lambda index: index.row())

    def _drag_accept(self, event):
        accepted = False
        if event.source() is self.view:
            accepted = True
        elif event.mimeData().hasUrls():
            # Only allow a list of supported local files.
            for url in event.mimeData().urls():
                if not url.isLocalFile():
                    break
                filename = url.toLocalFile()
                extension = os.path.splitext(filename)[1].lower()[1:]
                if extension not in _dictionary_formats():
                    break
            else:
                accepted = True
        if accepted:
            event.accept()
        return accepted

    def _drag_enter_event(self, event):
        self._drag_accept(event)

    def _drag_move_event(self, event):
        self._drag_accept(event)

    def _drag_drop_event(self, event):
        if not self._drag_accept(event):
            return
        index = self.view.indexAt(event.pos())
        if event.source() == self.view:
            self._model.move(index, self._selected)
        else:
            path_list = [url.toLocalFile() for url in event.mimeData().urls()]
            self._model.insert(index, path_list)

    def _get_dictionary_save_name(
        self, title, default_name=None, default_extensions=(), initial_filename=None
    ):
        if default_name is not None:
            # Default to a writable dictionary format.
            writable_extensions = set(_dictionary_formats(include_readonly=False))
            default_name += "." + next(
                (e for e in default_extensions if e in writable_extensions), "json"
            )
            default_name = os.path.join(self._file_dialogs_directory, default_name)
        else:
            default_name = self._file_dialogs_directory
        default_name = normalize_path(default_name)
        new_filename = QFileDialog.getSaveFileName(
            parent=self,
            caption=title,
            dir=default_name,
            filter=_dictionary_filters(include_readonly=False),
        )[0]
        if not new_filename:
            return None
        new_filename = normalize_path(new_filename)
        self._file_dialogs_directory = os.path.dirname(new_filename)
        if new_filename == initial_filename:
            return None
        return new_filename

    def _edit_dictionaries(self, index_list):
        path_list = [d.path for d in self._model.iter_loaded(index_list)]
        if not path_list:
            return
        editor = DictionaryEditor(self._engine, path_list)
        editor.exec()

    def _copy_dictionaries(self, dictionaries):
        need_reload = False
        # i18n: Widget: “DictionariesWidget”, “save as copy” file picker.
        title_template = _("Save a copy of {name} as...")
        # i18n: Widget: “DictionariesWidget”, “save as copy” file picker.
        default_name_template = _("{name} - Copy")
        for original in dictionaries:
            title = title_template.format(name=os.path.basename(original.path))
            name, ext = os.path.splitext(os.path.basename(original.path))
            default_name = default_name_template.format(name=name)
            new_filename = self._get_dictionary_save_name(
                title, default_name, [ext[1:]], initial_filename=original.path
            )
            if new_filename is None:
                continue
            with _new_dictionary(new_filename) as copy:
                copy.update(original)
            need_reload = True
        return need_reload

    def _merge_dictionaries(self, dictionaries):
        names, exts = zip(
            *(os.path.splitext(os.path.basename(d.path)) for d in dictionaries)
        )
        default_name = " + ".join(names)
        default_exts = list(dict.fromkeys(e[1:] for e in exts))
        # i18n: Widget: “DictionariesWidget”, “save as merge” file picker.
        title = _("Merge {names} as...").format(names=default_name)
        new_filename = self._get_dictionary_save_name(title, default_name, default_exts)
        if new_filename is None:
            return False
        with _new_dictionary(new_filename) as merge:
            # Merge in reverse priority order, so higher
            # priority entries overwrite lower ones.
            for source in reversed(dictionaries):
                merge.update(source)
        return True

    def _save_dictionaries(self, merge=False):
        # Ignore dictionaries that are not loaded.
        dictionaries = list(self._model.iter_loaded(self._selected))
        if not dictionaries:
            return
        if merge:
            save_fn = self._merge_dictionaries
        else:
            save_fn = self._copy_dictionaries
        if save_fn(dictionaries):
            # This will trigger a reload of any modified dictionary.
            self._engine.config = {}

    @Slot()
    def open_open_dictionaries_dialog(self):
        new_filenames = QFileDialog.getOpenFileNames(
            # i18n: Widget: “DictionariesWidget”, “add” file picker.
            parent=self,
            caption=_("Load dictionaries"),
            dir=self._file_dialogs_directory,
            filter=_dictionary_filters(),
        )[0]
        if not new_filenames:
            return
        self._file_dialogs_directory = os.path.dirname(new_filenames[-1])
        self._model.add(new_filenames)

    @Slot()
    def open_create_new_dictionary_dialog(self):
        # i18n: Widget: “DictionariesWidget”, “new” file picker.
        new_filename = self._get_dictionary_save_name(_("Create dictionary"))
        if new_filename is None:
            return
        with _new_dictionary(new_filename):
            pass
        self._model.add([new_filename])

    @Slot()
    def copy_selected_dictionaries(self):
        self._save_dictionaries()

    @Slot()
    def merge_selected_dictionaries(self):
        self._save_dictionaries(merge=True)

    @Slot(QModelIndex)
    def activate_dictionary(self, index):
        self._edit_dictionaries([index])

    @Slot()
    def open_add_dictionaries_menu(self):
        self.menu_AddDictionaries.exec(QCursor.pos())

    @Slot()
    def add_translation(self):
        dictionary = next(self._model.iter_loaded([self.view.currentIndex()]), None)
        self.signal_add_translation.emit(
            None if dictionary is None else dictionary.path
        )

    @Slot()
    def edit_selected_dictionaries(self):
        self._edit_dictionaries(self._selected)

    @Slot(bool)
    def toggle_undo_action(self, available):
        self.action_Undo.setEnabled(available)

    @Slot()
    def move_selected_dictionaries_down(self):
        self._model.move_down(self._selected)

    @Slot()
    def move_selected_dictionaries_up(self):
        self._model.move_up(self._selected)

    @Slot()
    def remove_selected_dictionaries(self):
        self._model.remove(self._selected)

    @Slot()
    def handle_selection_change(self):
        selection = self._selected
        has_selection = bool(selection)
        for widget in (
            self.action_RemoveDictionaries,
            self.action_MoveDictionariesUp,
            self.action_MoveDictionariesDown,
        ):
            widget.setEnabled(has_selection)
        has_live_selection = next(self._model.iter_loaded(selection), None) is not None
        for widget in (
            self.action_EditDictionaries,
            self.action_SaveDictionaries,
            self.menu_SaveDictionaries,
        ):
            widget.setEnabled(has_live_selection)

    @Slot()
    def undo(self):
        self._model.undo()
