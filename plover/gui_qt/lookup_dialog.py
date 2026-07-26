from PySide6.QtCore import QEvent, Qt, Slot

from plover import _
from plover.gui_qt.lookup_dialog_ui import Ui_LookupDialog
from plover.gui_qt.tool import Tool
from plover.translation import unescape_translation


class LookupDialog(Tool, Ui_LookupDialog):
    # i18n: Widget: “LookupDialog”, tooltip.
    __doc__ = _("Search the dictionary for translations.")

    TITLE = _("Lookup")
    ICON = ":/resources/lookup.svg"
    ROLE = "lookup"
    SHORTCUT = "Ctrl+L"

    def __init__(self, engine):
        super().__init__(engine)
        self.setupUi(self)
        self.pattern.installEventFilter(self)
        self.suggestions.installEventFilter(self)
        self.pattern.setFocus()
        self.restore_state()
        self.finished.connect(self.save_state)

    def eventFilter(self, watched, event):
        return bool(
            event.type() == QEvent.Type.KeyPress
            and event.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return)
        )

    def _update_suggestions(self, suggestion_list):
        self.suggestions.clear()
        self.suggestions.append(suggestion_list)

    @Slot(str)
    def lookup(self, pattern):
        translation = unescape_translation(pattern.strip())
        suggestion_list = self._engine.get_suggestions(translation)
        self._update_suggestions(suggestion_list)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.ActivationChange and self.isActiveWindow():
            self.pattern.setFocus()
            self.pattern.selectAll()
