from collections import namedtuple
from html import escape as html_escape
from os.path import split as os_path_split

from PySide6.QtCore import QEvent, Signal, Slot
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication, QWidget

from plover import _
from plover.misc import shorten_path
from plover.steno import normalize_steno, sort_steno_strokes
from plover.engine import StartingStrokeState
from plover.translation import escape_translation, unescape_translation
from plover.formatting import RetroFormatter
from plover.resource import resource_filename

from plover.formatting import SPACE_PLACEMENT_BEFORE
from plover.gui_qt.add_translation_widget_ui import Ui_AddTranslationWidget
from plover.gui_qt.steno_validator import StenoValidator


class AddTranslationWidget(QWidget, Ui_AddTranslationWidget):
    # i18n: Widget: “AddTranslationWidget”, tooltip.
    __doc__ = _("Add a new translation to the dictionary.")

    EngineState = namedtuple(
        "EngineState", "dictionary_filter translator starting_stroke"
    )

    mappingValid = Signal(bool)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        engine = QApplication.instance().engine
        self._engine = engine
        self._dictionaries = []
        self._reverse_order = False
        self._selected_dictionary = None
        self._mapping_is_valid = False
        engine.signal_connect("config_changed", self.on_config_changed)
        self.on_config_changed(engine.config)
        engine.signal_connect("dictionaries_loaded", self.on_dictionaries_loaded)
        self.on_dictionaries_loaded(self._engine.dictionaries)

        fixed_family = QFontDatabase.systemFont(
            QFontDatabase.SystemFont.FixedFont
        ).family()

        self._special_fmt = f'<span style="font-family:{fixed_family};">%s</span>'
        self._special_fmt_bold = (
            f'<span style="font-family:{fixed_family};font-weight:bold;">%s</span>'
        )

        self.strokes.setValidator(StenoValidator())
        self.strokes.installEventFilter(self)
        self.translation.installEventFilter(self)

        with engine:
            # Pre-populate the strokes or translations with last stroke/word.
            last_translations = engine.translator_state.translations
            translation = None
            for t in reversed(last_translations):
                # Find the last undoable stroke.
                if t.has_undo():
                    translation = t
                    break
            # Is it a raw stroke?
            if translation is not None and not translation.english:
                # Yes.
                self.strokes.setText(translation.formatting[0].text)
                self.handle_stroke_input_change()
                self.strokes.selectAll()
            else:
                # No, grab the last-formatted word.
                retro_formatter = RetroFormatter(last_translations)
                last_words = retro_formatter.last_words(strip=True)
                if last_words:
                    self.translation.setText(last_words[0])
                    self.handle_translation_input_change()

            self._original_state = self.EngineState(
                None, engine.translator_state, engine.starting_stroke_state
            )
            engine.clear_translator_state()
            self._strokes_state = self.EngineState(
                self._dictionary_filter,
                engine.translator_state,
                StartingStrokeState(True, False, "/", SPACE_PLACEMENT_BEFORE),
            )
            engine.clear_translator_state()
            self._translations_state = self.EngineState(
                None, engine.translator_state, StartingStrokeState(True, False, " ")
            )
        self._engine_state = self._original_state
        self._focus = None

    @property
    def mapping_is_valid(self):
        return self._mapping_is_valid

    def select_dictionary(self, dictionary_path):
        self._selected_dictionary = dictionary_path
        self._update_items()

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.FocusIn:
            if watched == self.strokes:
                self._focus_strokes()
            elif watched == self.translation:
                self._focus_translation()
        elif event.type() == QEvent.Type.FocusOut:
            if watched in (self.strokes, self.translation):
                self._unfocus()
        return False

    def _set_engine_state(self, state):
        with self._engine as engine:
            prev_state = self._engine_state
            if prev_state is not None and prev_state.dictionary_filter is not None:
                engine.remove_dictionary_filter(prev_state.dictionary_filter)
            engine.translator_state = state.translator
            engine.starting_stroke_state = state.starting_stroke
            if state.dictionary_filter is not None:
                engine.add_dictionary_filter(state.dictionary_filter)
            self._engine_state = state

    @staticmethod
    def _dictionary_filter(key, value):
        # Allow undo...
        if value == "=undo":
            return False
        # ...and translations with special entries. Do this by looking for
        # braces but take into account escaped braces and slashes.
        escaped = value.replace("\\\\", "").replace("\\{", "")
        special = "{#" in escaped or "{PLOVER:" in escaped
        return not special

    def _unfocus(self):
        self._unfocus_strokes()
        self._unfocus_translation()

    def _focus_strokes(self):
        if self._focus == "strokes":
            return
        self._unfocus_translation()
        self._set_engine_state(self._strokes_state)
        self._focus = "strokes"

    def _unfocus_strokes(self):
        if self._focus != "strokes":
            return
        self._set_engine_state(self._original_state)
        self._focus = None

    def _focus_translation(self):
        if self._focus == "translation":
            return
        self._unfocus_strokes()
        self._set_engine_state(self._translations_state)
        self._focus = "translation"

    def _unfocus_translation(self):
        if self._focus != "translation":
            return
        self._set_engine_state(self._original_state)
        self._focus = None

    def _strokes(self):
        strokes = self.strokes.text().strip()
        has_prefix = strokes.startswith("/")
        strokes = "/".join(strokes.replace("/", " ").split())
        if has_prefix:
            strokes = "/" + strokes
        strokes = normalize_steno(strokes)
        return strokes

    def _translation(self):
        translation = self.translation.text().strip()
        return unescape_translation(translation)

    def _update_items(self, dictionaries=None, reverse_order=None):
        if dictionaries is not None:
            self._dictionaries = dictionaries
        if reverse_order is not None:
            self._reverse_order = reverse_order
        iterable = self._dictionaries
        if self._reverse_order:
            iterable = reversed(iterable)
        self.dictionary.clear()
        for d in iterable:
            item = shorten_path(d.path)
            if not d.enabled:
                # i18n: Widget: “AddTranslationWidget”.
                item = _("{dictionary} (disabled)").format(dictionary=item)
            self.dictionary.addItem(item)
        selected_index = 0
        if self._selected_dictionary is None:
            # No user selection, select first enabled dictionary.
            for n, d in enumerate(self._dictionaries):
                if d.enabled:
                    selected_index = n
                    break
        else:
            # Keep user selection.
            for n, d in enumerate(self._dictionaries):
                if d.path == self._selected_dictionary:
                    selected_index = n
                    break
        if self._reverse_order:
            selected_index = self.dictionary.count() - selected_index - 1
        self.dictionary.setCurrentIndex(selected_index)

    def on_dictionaries_loaded(self, dictionaries):
        # We only care about loaded writable dictionaries.
        dictionaries = [d for d in dictionaries.dicts if not d.readonly]
        if dictionaries != self._dictionaries:
            self._update_items(dictionaries=dictionaries)

    def on_config_changed(self, config_update):
        if "classic_dictionaries_display_order" in config_update:
            self._update_items(
                reverse_order=config_update["classic_dictionaries_display_order"]
            )

    @Slot(int)
    def update_selected_dictionary(self, index):
        if self._reverse_order:
            index = len(self._dictionaries) - index - 1
        self._selected_dictionary = self._dictionaries[index].path

    def _format_label(self, fmt, strokes, translation=None, filename=None):
        if strokes:
            strokes = ", ".join(
                self._special_fmt % html_escape("/".join(s))
                for s in sort_steno_strokes(strokes)
            )
        if translation:
            translation = self._special_fmt_bold % html_escape(
                escape_translation(translation)
            )

        if filename:
            filename = html_escape(filename)

        return fmt.format(strokes=strokes, translation=translation, filename=filename)

    @Slot()
    def handle_stroke_input_change(self):
        mapping_is_valid = self.strokes.hasAcceptableInput()
        if mapping_is_valid != self._mapping_is_valid:
            self._mapping_is_valid = mapping_is_valid
            self.mappingValid.emit(mapping_is_valid)
        if not mapping_is_valid:
            return
        strokes = self._strokes()
        if strokes:
            translations = self._engine.raw_lookup_from_all(strokes)
            if translations:
                # i18n: Widget: “AddTranslationWidget”.
                info = self._format_label(_("{strokes} maps to "), (strokes,))
                entries = [
                    self._format_label(
                        ("• " if i else "") + "<bf>{translation}<bf/>\t({filename})",
                        None,
                        translation,
                        os_path_split(resource_filename(dictionary.path))[1],
                    )
                    for i, (translation, dictionary) in enumerate(translations)
                ]
                if len(entries) > 1:
                    # i18n: Widget: “AddTranslationWidget”.
                    entries.insert(1, "<br />" + _("Overwritten entries:"))
                info += "<br />".join(entries)
            else:
                info = self._format_label(
                    # i18n: Widget: “AddTranslationWidget”.
                    _("{strokes} is not mapped in any dictionary"),
                    (strokes,),
                )
        else:
            info = ""
        self.strokes_info.setText(info)

    @Slot()
    def handle_translation_input_change(self):
        translation = self._translation()
        if translation:
            strokes = self._engine.reverse_lookup(translation)
            if strokes:
                # i18n: Widget: “AddTranslationWidget”.
                fmt = _("{translation} is mapped to: {strokes}")
            else:
                # i18n: Widget: “AddTranslationWidget”.
                fmt = _("{translation} is not in the dictionary")
            info = self._format_label(fmt, strokes, translation)
        else:
            info = ""
        self.translation_info.setText(info)

    def save_entry(self):
        self._unfocus()
        strokes = self._strokes()
        translation = self._translation()
        if strokes and translation:
            index = self.dictionary.currentIndex()
            if self._reverse_order:
                index = -index - 1
            dictionary = self._dictionaries[index]
            old_translation = self._engine.dictionaries[dictionary.path].get(strokes)
            self._engine.add_translation(
                strokes, translation, dictionary_path=dictionary.path
            )
            return dictionary, strokes, old_translation, translation

    def reject(self):
        self._unfocus()
        self._set_engine_state(self._original_state)
