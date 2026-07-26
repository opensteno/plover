from collections import namedtuple
from itertools import chain
from operator import attrgetter, itemgetter

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Slot
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QStyledItemDelegate,
)

from plover import _
from plover.gui_qt.dictionary_editor_ui import Ui_DictionaryEditor
from plover.gui_qt.steno_validator import StenoValidator
from plover.gui_qt.utils import ToolBar, WindowStateMixin
from plover.misc import expand_path, shorten_path
from plover.steno import normalize_steno, steno_to_sort_key
from plover.translation import escape_translation, unescape_translation

_COL_STENO, _COL_TRANS, _COL_DICT, _COL_COUNT = range(3 + 1)


class DictionaryItem(namedtuple("DictionaryItem", "steno translation dictionary")):
    @property
    def strokes(self):
        return normalize_steno(self.steno, strict=False)

    @property
    def dictionary_path(self):
        return self.dictionary.path


class DictionaryItemDelegate(QStyledItemDelegate):
    def __init__(self, dictionary_list):
        super().__init__()
        self._dictionary_list = dictionary_list

    def createEditor(self, parent, option, index):
        if index.column() == _COL_DICT:
            dictionary_paths = [
                shorten_path(dictionary.path)
                for dictionary in self._dictionary_list
                if not dictionary.readonly
            ]
            combo = QComboBox(parent)
            combo.addItems(dictionary_paths)
            return combo
        widget = super().createEditor(parent, option, index)
        if index.column() == _COL_STENO:
            widget.setValidator(StenoValidator())
        return widget


class DictionaryItemModel(QAbstractTableModel):
    def __init__(self, dictionary_list, sort_column, sort_order):
        super().__init__()
        self._error_icon = QIcon(":resources/dictionary_error.svg")
        self._dictionary_list = dictionary_list
        self._operations = []
        self._entries = []
        self._sort_column = sort_column
        self._sort_order = sort_order
        self._update_entries()

    def _update_entries(self, strokes_filter=None, translation_filter=None):
        self._entries = []
        for dictionary in self._dictionary_list:
            for strokes, translation in dictionary.items():
                steno = "/".join(strokes)
                if strokes_filter is not None and not steno.startswith(strokes_filter):
                    continue
                if translation_filter is not None and not translation.startswith(
                    translation_filter
                ):
                    continue
                item = DictionaryItem(steno, translation, dictionary)
                self._entries.append(item)
        self.sort(self._sort_column, self._sort_order)

    @property
    def has_undo(self):
        return bool(self._operations)

    @property
    def modified(self):
        paths = set()
        dictionary_list = []
        for op_list in self._operations:
            if not isinstance(op_list, list):
                op_list = (op_list,)
            for item in chain(*op_list):
                if item is None:
                    continue
                dictionary = item.dictionary
                if dictionary.path in paths:
                    continue
                paths.add(dictionary.path)
                dictionary_list.append(dictionary)
        return dictionary_list

    # Note:
    # - since switching from a dictionary to a table does not enforce the
    #   unicity of keys, a deletion can fail when one of the duplicate has
    #   already been deleted.
    # - when undoing an operation at the table level, the item may have
    #   been filtered-out and not present

    def _undo(self, old_item, new_item):
        if old_item is None:
            # Undo addition.
            try:
                del new_item.dictionary[new_item.strokes]
            except KeyError:
                pass
            try:
                row = self._entries.index(new_item)
            except ValueError:
                # Happen if the item is filtered-out.
                pass
            else:
                self.remove_rows([row], record=False)
            return
        if new_item is None:
            # Undo deletion.
            self.new_row(0, item=old_item, record=False)
            return
        # Undo update.
        try:
            del new_item.dictionary[new_item.strokes]
        except KeyError:
            pass
        try:
            row = self._entries.index(new_item)
        except ValueError:
            # Happen if the item is filtered-out,
            # "create" a new row so the user see
            # the result of the undo.
            self.new_row(0, item=old_item, record=False)
        else:
            old_item.dictionary[old_item.strokes] = old_item.translation
            self._entries[row] = old_item
            self.dataChanged.emit(
                self.index(row, _COL_STENO), self.index(row, _COL_TRANS)
            )

    def undo(self, op=None):
        op = self._operations.pop()
        if isinstance(op, list):
            for old_item, new_item in op:
                self._undo(old_item, new_item)
        else:
            self._undo(*op)

    def rowCount(self, parent):
        return 0 if parent.isValid() else len(self._entries)

    def columnCount(self, parent):
        return _COL_COUNT

    def headerData(self, section, orientation, role):
        if (
            orientation != Qt.Orientation.Horizontal
            or role != Qt.ItemDataRole.DisplayRole
        ):
            return None
        if section == _COL_STENO:
            # i18n: Widget: “DictionaryEditor”.
            return _("Strokes")
        if section == _COL_TRANS:
            # i18n: Widget: “DictionaryEditor”.
            return _("Translation")
        if section == _COL_DICT:
            # i18n: Widget: “DictionaryEditor”.
            return _("Dictionary")

    def data(self, index, role):
        if not index.isValid() or role not in (
            Qt.ItemDataRole.EditRole,
            Qt.ItemDataRole.DisplayRole,
            Qt.ItemDataRole.DecorationRole,
        ):
            return None
        item = self._entries[index.row()]
        column = index.column()
        if role == Qt.ItemDataRole.DecorationRole:
            if column == _COL_STENO:
                try:
                    normalize_steno(item.steno)
                except ValueError:
                    return self._error_icon
            return None
        if column == _COL_STENO:
            return item.steno
        if column == _COL_TRANS:
            return escape_translation(item.translation)
        if column == _COL_DICT:
            return shorten_path(item.dictionary.path)

    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags
        f = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        item = self._entries[index.row()]
        if not item.dictionary.readonly:
            f |= Qt.ItemFlag.ItemIsEditable
        return f

    def filter(self, strokes_filter=None, translation_filter=None):
        self.modelAboutToBeReset.emit()
        self._update_entries(strokes_filter, translation_filter)
        self.modelReset.emit()

    @staticmethod
    def _item_steno_sort_key(item):
        return steno_to_sort_key(item[_COL_STENO], strict=False)

    def sort(self, column, order):
        self.layoutAboutToBeChanged.emit()
        if column == _COL_DICT:
            key = attrgetter("dictionary_path")
        elif column == _COL_STENO:
            key = self._item_steno_sort_key
        else:
            key = itemgetter(column)
        self._entries.sort(key=key, reverse=(order == Qt.SortOrder.DescendingOrder))
        self._sort_column = column
        self._sort_order = order
        self.layoutChanged.emit()

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole, record=True):
        assert role == Qt.ItemDataRole.EditRole
        row = index.row()
        column = index.column()
        old_item = self._entries[row]
        strokes = old_item.strokes
        steno, translation, dictionary = old_item
        if column == _COL_STENO:
            strokes = normalize_steno(value.strip(), strict=False)
            steno = "/".join(strokes)
            if not steno or steno == old_item.steno:
                return False
        elif column == _COL_TRANS:
            translation = unescape_translation(value.strip())
            if translation == old_item.translation:
                return False
        elif column == _COL_DICT:
            path = expand_path(value)
            for dictionary in self._dictionary_list:
                if dictionary.path == path:
                    break
            if dictionary == old_item.dictionary:
                return False
        try:
            del old_item.dictionary[old_item.strokes]
        except KeyError:
            pass
        # Merge operations when editing a newly added row.
        if (
            not old_item.strokes
            and not old_item.translation
            and self._operations
            and self._operations[-1] == [(None, old_item)]
        ):
            self._operations.pop()
            old_item = None
        new_item = DictionaryItem(steno, translation, dictionary)
        self._entries[row] = new_item
        dictionary[strokes] = translation
        if record:
            self._operations.append((old_item, new_item))
        self.dataChanged.emit(index, index)
        return True

    def new_row(self, row, item=None, record=True):
        if item is None:
            if row == 0 and not self._entries:
                dictionary = self._dictionary_list[0]
            else:
                dictionary = self._entries[row].dictionary
            item = DictionaryItem("", "", dictionary)
        self.beginInsertRows(QModelIndex(), row, row)
        self._entries.insert(row, item)
        if record:
            self._operations.append((None, item))
        self.endInsertRows()

    def remove_rows(self, row_list, record=True):
        assert row_list
        operations = []
        for row in sorted(row_list, reverse=True):
            self.beginRemoveRows(QModelIndex(), row, row)
            item = self._entries.pop(row)
            self.endRemoveRows()
            try:
                del item.dictionary[item.strokes]
            except KeyError:
                pass
            else:
                operations.append((item, None))
        if record:
            self._operations.append(operations)


class DictionaryEditor(QDialog, Ui_DictionaryEditor, WindowStateMixin):
    ROLE = "dictionary_editor"

    def __init__(self, engine, dictionary_paths):
        super().__init__()
        self.setupUi(self)
        self._engine = engine
        with engine:
            dictionary_list = [
                dictionary
                for dictionary in engine.dictionaries.dicts
                if dictionary.path in dictionary_paths
            ]
        sort_column, sort_order = _COL_STENO, Qt.SortOrder.AscendingOrder
        self._model = DictionaryItemModel(dictionary_list, sort_column, sort_order)
        self._model.dataChanged.connect(self.update_after_data_change)
        self.table.sortByColumn(sort_column, sort_order)
        self.table.setSortingEnabled(True)
        self.table.setModel(self._model)
        self.table.resizeColumnsToContents()
        self.table.setItemDelegate(DictionaryItemDelegate(dictionary_list))
        self.table.selectionModel().selectionChanged.connect(
            self.handle_selection_change
        )
        background = self.table.palette().highlightedText().color().name()
        text_color = self.table.palette().highlight().color().name()
        self.table.setStyleSheet(
            f"""
                                 QTableView::item:focus {{
                                     background-color: {background};
                                     color: {text_color};
                                }}"""
        )
        self.table.setFocus()
        for action in (
            self.action_Undo,
            self.action_Delete,
        ):
            action.setEnabled(False)
        # Toolbar.
        self.layout().addWidget(
            ToolBar(
                self.action_Undo,
                self.action_Delete,
                self.action_New,
            )
        )
        self.strokes_filter.setValidator(StenoValidator())
        self.restore_state()
        self.finished.connect(self.save_state)

    @property
    def _selection(self):
        return sorted(
            index.row() for index in self.table.selectionModel().selectedRows(0)
        )

    def _select(self, row, edit=False):
        row = min(row, self._model.rowCount(QModelIndex()) - 1)
        index = self._model.index(row, 0)
        self.table.setCurrentIndex(index)
        if edit:
            self.table.edit(index)

    @Slot(QModelIndex, QModelIndex)
    def update_after_data_change(self, top_left, bottom_right):
        self.table.setCurrentIndex(top_left)
        self.action_Undo.setEnabled(self._model.has_undo)

    @Slot()
    def handle_selection_change(self):
        enabled = bool(self._selection)
        for action in (self.action_Delete,):
            action.setEnabled(enabled)

    @Slot()
    def undo(self):
        assert self._model.has_undo
        self._model.undo()
        self.action_Undo.setEnabled(self._model.has_undo)

    @Slot()
    def delete_selected_row(self):
        selection = self._selection
        assert selection
        self._model.remove_rows(selection)
        self._select(selection[0])
        self.action_Undo.setEnabled(self._model.has_undo)

    @Slot()
    def add_new_row(self):
        selection = self._selection
        if selection:
            row = self._selection[0]
        else:
            row = 0
        self.table.reset()
        self._model.new_row(row)
        self._select(row, edit=True)
        self.action_Undo.setEnabled(self._model.has_undo)

    @Slot()
    def apply_filter(self):
        self.table.selectionModel().clear()
        strokes_filter = "/".join(normalize_steno(self.strokes_filter.text().strip()))
        translation_filter = unescape_translation(
            self.translation_filter.text().strip()
        )
        self._model.filter(
            strokes_filter=strokes_filter, translation_filter=translation_filter
        )

    @Slot()
    def clear_filter(self):
        self.strokes_filter.setText("")
        self.translation_filter.setText("")
        self._model.filter(strokes_filter=None, translation_filter=None)

    @Slot(int)
    def save_modified_dictionaries(self, result):
        with self._engine:
            self._engine.dictionaries.save(
                dictionary.path for dictionary in self._model.modified
            )
