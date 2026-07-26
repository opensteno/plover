from PySide6.QtWidgets import QDialogButtonBox

from plover import _
from plover.gui_qt.add_translation_dialog_ui import Ui_AddTranslationDialog
from plover.gui_qt.tool import Tool


class AddTranslationDialog(Tool, Ui_AddTranslationDialog):
    # i18n: Widget: “AddTranslationDialog”, tooltip.
    __doc__ = _("Add a new translation to the dictionary.")

    TITLE = _("Add Translation")
    ICON = ":/resources/translation_add.svg"
    ROLE = "add_translation"
    SHORTCUT = "Ctrl+N"

    def __init__(self, engine, dictionary_path=None):
        super().__init__(engine)
        self.setupUi(self)
        self.add_translation.select_dictionary(dictionary_path)
        self.add_translation.mappingValid.connect(self.on_mapping_valid)
        self.on_mapping_valid(self.add_translation.mapping_is_valid)
        engine.signal_connect("config_changed", self.on_config_changed)
        self.on_config_changed(engine.config)
        self.installEventFilter(self)
        self.restore_state()
        self.finished.connect(self.save_state)

    def on_mapping_valid(self, valid):
        self.buttonBox.button(QDialogButtonBox.StandardButton.Ok).setEnabled(valid)

    def on_config_changed(self, config_update):
        if "translation_frame_opacity" in config_update:
            opacity = config_update.get("translation_frame_opacity")
            if opacity is None:
                return
            assert 0 <= opacity <= 100
            self.setWindowOpacity(opacity / 100.0)

    def accept(self):
        self.add_translation.save_entry()
        super().accept()

    def reject(self):
        self.add_translation.reject()
        super().reject()
