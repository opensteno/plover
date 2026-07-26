import re

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import (
    QAction,
    QCursor,
    QFont,
)
from PySide6.QtWidgets import (
    QFontDialog,
    QMenu,
)

from plover import _
from plover.formatting import RetroFormatter
from plover.gui_qt import utils
from plover.gui_qt.suggestions_dialog_ui import Ui_SuggestionsDialog
from plover.gui_qt.tool import Tool
from plover.gui_qt.utils import ToolBar
from plover.suggestions import Suggestion


class SuggestionsDialog(Tool, Ui_SuggestionsDialog):
    # i18n: Widget: “SuggestionsDialog”, tooltip.
    __doc__ = _("Suggest possible strokes for the last written words.")

    TITLE = _("Suggestions")
    ICON = ":/resources/lightbulb.svg"
    ROLE = "suggestions"
    SHORTCUT = "Ctrl+J"

    WORD_RX = re.compile(r"(?:\w+|[^\w\s]+)\s*")

    STYLE_TRANSLATION, STYLE_STROKES = range(2)

    # Anatomy of the text document:
    # - "root" frame:
    #  - 0+ "suggestions" frames
    #   - 1+ "translation" frames
    #    - 1-10 "strokes" frames

    def __init__(self, engine):
        super().__init__(engine)
        self.setupUi(self)
        self._last_suggestions = None
        # Toolbar.
        actions = [
            self.action_SelectFont,
            self.action_Clear,
        ]
        if not utils.is_wayland():
            # Wayland does not support window on top.
            actions.insert(0, self.action_ToggleOnTop)

        self.layout().addWidget(ToolBar(*actions))

        self.action_Clear.setEnabled(False)
        # Font popup menu.
        self._font_menu = QMenu()
        # i18n: Widget: “SuggestionsDialog”, “font” menu.
        self._font_menu_text = QAction(_("&Text"), self._font_menu)
        # i18n: Widget: “SuggestionsDialog”, “font” menu.
        self._font_menu_strokes = QAction(_("&Strokes"), self._font_menu)
        self._font_menu.addActions([self._font_menu_text, self._font_menu_strokes])
        engine.signal_connect("translated", self.on_translation)
        self.suggestions.setFocus()
        self.restore_state()
        self.finished.connect(self.save_state)

    def _get_font(self, name):
        return getattr(self.suggestions, name)

    def _set_font(self, name, font):
        setattr(self.suggestions, name, font)

    def _restore_state(self, settings):
        for name in (
            "text_font",
            "strokes_font",
        ):
            font_string = settings.value(name)
            if font_string is None:
                continue
            font = QFont()
            if not font.fromString(font_string):
                continue
            self._set_font(name, font)
        ontop = settings.value("ontop", None, bool)
        if ontop is not None:
            self.action_ToggleOnTop.setChecked(ontop)
            self.toggle_ontop(ontop)

    def _save_state(self, settings):
        for name in (
            "text_font",
            "strokes_font",
        ):
            font = self._get_font(name)
            font_string = font.toString()
            settings.setValue(name, font_string)
        ontop = bool(self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        settings.setValue("ontop", ontop)

    def _show_suggestions(self, suggestion_list):
        self.suggestions.append(suggestion_list)
        self.action_Clear.setEnabled(True)

    @staticmethod
    def tails(ls):
        """Return all tail combinations (a la Haskell)

        tails :: [x] -> [[x]]
        >>> tails('abcd')
        ['abcd', 'bcd', 'cd', d']

        """

        for i in range(len(ls)):
            yield ls[i:]

    def on_translation(self, old, new):
        # Check for new output.
        for a in reversed(new):
            if a.text and not a.text.isspace():
                break
        else:
            return

        # Get the last 10 words.
        with self._engine:
            last_translations = self._engine.translator_state.translations
            retro_formatter = RetroFormatter(last_translations)
            split_words = retro_formatter.last_words(10, rx=self.WORD_RX)

        suggestion_list = []
        for phrase in self.tails(split_words):
            phrase = "".join(phrase)
            suggestion_list.extend(self._engine.get_suggestions(phrase))

        if not suggestion_list and split_words:
            suggestion_list = [Suggestion(split_words[-1], [])]

        if suggestion_list and suggestion_list != self._last_suggestions:
            self._last_suggestions = suggestion_list
            self._show_suggestions(suggestion_list)

    @Slot()
    def select_font(self):
        action = self._font_menu.exec(QCursor.pos())
        if action is None:
            return
        if action == self._font_menu_text:
            name = "text_font"
        elif action == self._font_menu_strokes:
            name = "strokes_font"
        font = self._get_font(name)
        ok, font = QFontDialog.getFont(font, self, "")
        if ok:
            self._set_font(name, font)

    @Slot(bool)
    def toggle_ontop(self, ontop):
        self.setWindowFlag(Qt.WindowStaysOnTopHint, ontop)
        self.show()

    @Slot()
    def clear(self):
        self.action_Clear.setEnabled(False)
        self._last_suggestions = None
        self.suggestions.clear()
