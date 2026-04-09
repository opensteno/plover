from PySide6.QtCore import (
    QAbstractListModel,
    QMimeData,
    QModelIndex,
    Qt,
)
from PySide6.QtGui import (
    QFont,
    QFontMetrics,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
)
from PySide6.QtWidgets import (
    QListView,
    QStyle,
    QStyledItemDelegate,
)

from plover import _
from plover.translation import escape_translation

from .utils import ActionCopyViewSelectionToClipboard


# i18n: Widget: “SuggestionsWidget”.
NO_SUGGESTIONS_STRING = _("no suggestions")
MAX_SUGGESTIONS_COUNT = 10


class SuggestionsDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._doc = QTextDocument()
        self._translation_char_format = QTextCharFormat()
        self._strokes_char_format = QTextCharFormat()
        self._strokes_char_format.font().setStyleHint(QFont.StyleHint.Monospace)
        self._size_hint_cache = {}

    def clear_size_hint_cache(self):
        self._size_hint_cache.clear()

    @property
    def text_font(self):
        return self._translation_char_format.font()

    @text_font.setter
    def text_font(self, font):
        self._translation_char_format.setFont(font)
        self.clear_size_hint_cache()

    @property
    def strokes_font(self):
        return self._strokes_char_format.font()

    @strokes_font.setter
    def strokes_font(self, font):
        self._strokes_char_format.setFont(font)
        self.clear_size_hint_cache()

    def _format_suggestion(self, index):
        suggestion = index.data(Qt.ItemDataRole.DisplayRole)
        translation = escape_translation(suggestion[0]) + ":"
        if not suggestion[1]:
            translation += " " + NO_SUGGESTIONS_STRING
            return translation, None
        strokes = ""
        for strokes_list in suggestion[1][:MAX_SUGGESTIONS_COUNT]:
            strokes += "\n    " + "/".join(strokes_list)
        return translation, strokes

    def _suggestion_size_hint(self, index):
        translation, strokes = self._format_suggestion(index)
        size = QFontMetrics(self.text_font).size(0, translation)
        if strokes is not None:
            size += QFontMetrics(self.strokes_font).size(0, strokes)
        return size

    def paint(self, painter, option, index):
        painter.save()
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
            text_color = option.palette.highlightedText()
        else:
            text_color = option.palette.text()
        self._translation_char_format.setForeground(text_color)
        self._strokes_char_format.setForeground(text_color)
        painter.translate(option.rect.topLeft())
        self._doc.clear()
        cursor = QTextCursor(self._doc)
        translation, strokes = self._format_suggestion(index)
        cursor.insertText(translation, self._translation_char_format)
        if strokes is not None:
            cursor.insertText(strokes, self._strokes_char_format)
        self._doc.drawContents(painter)
        painter.restore()

    def sizeHint(self, option, index):
        size = self._size_hint_cache.get(index.row())
        if size is not None:
            return size
        size = self._suggestion_size_hint(index)
        self._size_hint_cache[index.row()] = size
        return size


class SuggestionsModel(QAbstractListModel):
    def __init__(self):
        super().__init__()
        self._suggestion_list = []

    def rowCount(self, parent):
        return 0 if parent.isValid() else len(self._suggestion_list)

    def data(self, index, role):
        if not index.isValid():
            return None
        suggestion = self._suggestion_list[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return suggestion
        if role == Qt.ItemDataRole.AccessibleTextRole:
            translation = escape_translation(suggestion[0])
            if suggestion[1]:
                steno = ", ".join(
                    "/".join(strokes_list)
                    for strokes_list in suggestion[1][:MAX_SUGGESTIONS_COUNT]
                )
            else:
                steno = NO_SUGGESTIONS_STRING
            return translation + ": " + steno
        return None

    def clear(self):
        self.modelAboutToBeReset.emit()
        self._suggestion_list.clear()
        self.modelReset.emit()

    def extend(self, suggestion_list):
        row = len(self._suggestion_list)
        self.beginInsertRows(QModelIndex(), row, row + len(suggestion_list))
        self._suggestion_list.extend(suggestion_list)
        self.endInsertRows()

    def mimeTypes(self):
        return ["text/plain"]

    def mimeData(self, indexes):
        data = QMimeData()
        data.setText(
            "\n".join(
                filter(
                    None,
                    (
                        self.data(index, Qt.ItemDataRole.AccessibleTextRole)
                        for index in indexes
                    ),
                )
            )
        )
        return data


class SuggestionsWidget(QListView):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setResizeMode(self.ResizeMode.Adjust)
        self.setSelectionMode(self.SelectionMode.ExtendedSelection)
        self._copy_action = ActionCopyViewSelectionToClipboard(self)
        self.addAction(self._copy_action)
        self._model = SuggestionsModel()
        self._delegate = SuggestionsDelegate(self)
        self.setModel(self._model)
        self.setItemDelegate(self._delegate)

    def append(self, suggestion_list):
        scrollbar = self.verticalScrollBar()
        scroll_at_end = scrollbar.value() == scrollbar.maximum()
        self._model.extend(suggestion_list)
        if scroll_at_end:
            self.scrollToBottom()

    def clear(self):
        self._model.clear()
        self._delegate.clear_size_hint_cache()

    def _reformat(self):
        self._model.layoutAboutToBeChanged.emit()
        self._model.layoutChanged.emit()

    @property
    def text_font(self):
        return self._delegate.text_font

    @text_font.setter
    def text_font(self, font):
        self._delegate.text_font = font
        self._reformat()

    @property
    def strokes_font(self):
        return self._delegate.strokes_font

    @strokes_font.setter
    def strokes_font(self, font):
        self._delegate.strokes_font = font
        self._reformat()
