import time

from PySide6.QtCore import (
    QAbstractListModel,
    QMimeData,
    QModelIndex,
    Qt,
    Slot,
)
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import (
    QFileDialog,
    QFontDialog,
    QMessageBox,
)
from wcwidth import wcwidth

from plover import _, system
from plover.gui_qt import utils
from plover.gui_qt.paper_tape_ui import Ui_PaperTape
from plover.gui_qt.tool import Tool
from plover.gui_qt.utils import ActionCopyViewSelectionToClipboard, ToolBar
from plover.steno import Stroke

STYLE_PAPER, STYLE_RAW = (
    # i18n: Paper tape style.
    _("Paper"),
    # i18n: Paper tape style.
    _("Raw"),
)
TAPE_STYLES = (STYLE_PAPER, STYLE_RAW)


class TapeModel(QAbstractListModel):
    def __init__(self):
        super().__init__()
        self._stroke_list = []
        self._style = None
        self._all_keys = None
        self._numbers = None

    def rowCount(self, parent):
        return 0 if parent.isValid() else len(self._stroke_list)

    @property
    def style(self):
        return self._style

    @style.setter
    def style(self, style):
        assert style in TAPE_STYLES
        self.layoutAboutToBeChanged.emit()
        self._style = style
        self.layoutChanged.emit()

    def _paper_format(self, stroke):
        text = self._all_keys_filler * 1
        keys = stroke.steno_keys[:]
        if any(key in self._numbers for key in keys):
            keys.append("#")
        for key in keys:
            index = system.KEY_ORDER[key]
            text[index] = self._all_keys[index]
        return "".join(text)

    @staticmethod
    def _raw_format(stroke):
        return stroke.rtfcre

    def data(self, index, role):
        if not index.isValid():
            return None
        stroke = self._stroke_list[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            if self._style == STYLE_PAPER:
                return self._paper_format(stroke)
            if self._style == STYLE_RAW:
                return self._raw_format(stroke)
        if role == Qt.ItemDataRole.AccessibleTextRole:
            return stroke.rtfcre
        return None

    def reset(self):
        self.modelAboutToBeReset.emit()
        self._all_keys = "".join(key.strip("-") for key in system.KEYS)
        self._all_keys_filler = [" " * wcwidth(k) for k in self._all_keys]
        self._numbers = set(system.NUMBERS.values())
        self._stroke_list.clear()
        self.modelReset.emit()
        return self._all_keys

    def append(self, stroke):
        row = len(self._stroke_list)
        self.beginInsertRows(QModelIndex(), row, row)
        self._stroke_list.append(stroke)
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
                        self.data(index, Qt.ItemDataRole.DisplayRole)
                        for index in indexes
                    ),
                )
            )
        )
        return data


class PaperTape(Tool, Ui_PaperTape):
    # i18n: Widget: “PaperTape”, tooltip.
    __doc__ = _("Paper tape display of strokes.")

    TITLE = _("Paper Tape")
    ICON = ":/resources/tape.svg"
    ROLE = "paper_tape"
    SHORTCUT = "Ctrl+T"

    def __init__(self, engine):
        super().__init__(engine)
        self.setupUi(self)
        self._model = TapeModel()
        self.header.setContentsMargins(4, 0, 0, 0)
        self.styles.addItems(TAPE_STYLES)
        self.tape.setModel(self._model)

        # Set a OS‑native fixed‑width (monospace) font.
        fixed_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        fixed_font.setPointSize(fixed_font.pointSize() + 4)
        self.header.setFont(fixed_font)
        self.tape.setFont(fixed_font)

        self.tape.setSelectionMode(self.tape.SelectionMode.ExtendedSelection)
        self._copy_action = ActionCopyViewSelectionToClipboard(self.tape)
        self.tape.addAction(self._copy_action)
        # Toolbar.
        actions = [
            self.action_SelectFont,
            self.action_Clear,
            self.action_Save,
        ]
        if not utils.is_wayland():
            # Wayland does not support window on top.
            actions.insert(0, self.action_ToggleOnTop)

        self.layout().addWidget(ToolBar(*actions))
        self.action_Clear.setEnabled(False)
        self.action_Save.setEnabled(False)
        engine.signal_connect("config_changed", self.on_config_changed)
        self.on_config_changed(engine.config)
        engine.signal_connect("stroked", self.handle_stroke)
        self.tape.setFocus()
        self.restore_state()
        self.finished.connect(self.save_state)

    def _restore_state(self, settings):
        style = settings.value("style", None, int)
        if style is not None:
            style = TAPE_STYLES[style]
            self.styles.setCurrentText(style)
            self.change_style(style)
        font_string = settings.value("font")
        if font_string is not None:
            font = QFont()
            if font.fromString(font_string):
                self.header.setFont(font)
                self.tape.setFont(font)
        ontop = settings.value("ontop", None, bool)
        if ontop is not None:
            self.action_ToggleOnTop.setChecked(ontop)
            self.toggle_ontop(ontop)

    def _save_state(self, settings):
        settings.setValue("style", TAPE_STYLES.index(self._style))
        settings.setValue("font", self.tape.font().toString())
        ontop = bool(self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        settings.setValue("ontop", ontop)

    def on_config_changed(self, config):
        if "system_name" in config:
            all_keys = self._model.reset()
            self.header.setText(all_keys)

    @property
    def _scroll_at_end(self):
        scrollbar = self.tape.verticalScrollBar()
        return scrollbar.value() == scrollbar.maximum()

    @property
    def _style(self):
        return self.styles.currentText()

    @Slot(Stroke)
    def handle_stroke(self, stroke):
        scroll_at_end = self._scroll_at_end
        self._model.append(stroke)
        if scroll_at_end:
            self.tape.scrollToBottom()
        self.action_Clear.setEnabled(True)
        self.action_Save.setEnabled(True)

    @Slot(str)
    def change_style(self, style):
        assert style in TAPE_STYLES
        scroll_at_end = self._scroll_at_end
        self._model.style = style
        self.header.setVisible(style == STYLE_PAPER)
        if scroll_at_end:
            self.tape.scrollToBottom()

    @Slot()
    def select_font(self):
        ok, font = QFontDialog.getFont(self.tape.font(), self, "")
        if ok:
            self.header.setFont(font)
            self.tape.setFont(font)

    @Slot(bool)
    def toggle_ontop(self, ontop):
        self.setWindowFlag(Qt.WindowStaysOnTopHint, ontop)
        self.show()

    @Slot()
    def clear(self):
        flags = self.windowFlags()
        msgbox = QMessageBox()
        msgbox.setText(_("Do you want to clear the paper tape?"))
        msgbox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        # Make sure the message box ends up above the paper tape!
        msgbox.setWindowFlags(
            msgbox.windowFlags() | (flags & Qt.WindowType.WindowStaysOnTopHint)
        )
        if QMessageBox.Yes != msgbox.exec():
            return
        self._strokes = []
        self.action_Clear.setEnabled(False)
        self.action_Save.setEnabled(False)
        self._model.reset()

    @Slot()
    def save(self):
        filename_suggestion = "steno-notes-{}.txt".format(
            time.strftime("%Y-%m-%d-%H-%M")
        )
        filename = QFileDialog.getSaveFileName(
            self,
            _("Save Paper Tape"),
            filename_suggestion,
            # i18n: Paper tape, "save" file picker.
            _("Text files (*.txt)"),
        )[0]
        if not filename:
            return
        with open(filename, "w") as fp:
            for row in range(self._model.rowCount(self._model.index(-1, -1))):
                print(
                    self._model.data(
                        self._model.index(row, 0), Qt.ItemDataRole.DisplayRole
                    ),
                    file=fp,
                )
