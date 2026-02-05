from collections import ChainMap
from copy import copy
from functools import partial

from PySide6.QtCore import (
    Qt,
    Signal,
    Slot,
)
from typing import Set

from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHeaderView,
    QGroupBox,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
)

from plover import _
from plover.config import MINIMUM_UNDO_LEVELS, MINIMUM_TIME_BETWEEN_KEY_PRESSES
from plover.gui_qt import appearance
from plover.misc import expand_path, shorten_path
from plover.registry import registry
from plover.oslayer.config import PLATFORM

from plover.gui_qt.config_window_ui import Ui_ConfigWindow
from plover.gui_qt.config_file_widget_ui import Ui_FileWidget
from plover.gui_qt.utils import WindowStateMixin


class NopeOption(QLabel):
    valueChanged = Signal(bool)

    def __init__(self):
        super().__init__()
        # i18n: Widget: “NopeOption” (empty config option message,
        # e.g. the machine option when selecting the Treal machine).
        self.setText(_("Nothing to see here!"))

    def setValue(self, value):
        pass


class BooleanOption(QCheckBox):
    valueChanged = Signal(bool)

    def __init__(self):
        super().__init__()
        self.stateChanged.connect(lambda: self.valueChanged.emit(self.isChecked()))

    def setValue(self, value):
        self.setChecked(value)


class IntOption(QSpinBox):
    def __init__(self, maximum=None, minimum=None):
        super().__init__()
        if maximum is not None:
            self.setMaximum(maximum)
        if minimum is not None:
            self.setMinimum(minimum)


class ChoiceOption(QComboBox):
    valueChanged = Signal(str)

    def __init__(self, choices=None):
        super().__init__()
        choices = {} if choices is None else choices
        for value, label in sorted(choices.items()):
            self.addItem(label, value)
        self.activated.connect(self.on_activated)

    def setValue(self, value):
        self.setCurrentIndex(self.findData(value))

    def on_activated(self, index):
        self.valueChanged.emit(self.itemData(index))


class FileOption(QGroupBox, Ui_FileWidget):
    valueChanged = Signal(str)

    def __init__(self, dialog_title, dialog_filter):
        super().__init__()
        self._dialog_title = dialog_title
        self._dialog_filter = dialog_filter
        self.setupUi(self)

    def setValue(self, value):
        self.path.setText(shorten_path(value))

    @Slot()
    def open_file_dialog(self):
        filename_suggestion = self.path.text()
        filename = QFileDialog.getSaveFileName(
            self,
            self._dialog_title,
            filename_suggestion,
            self._dialog_filter,
        )[0]
        if not filename:
            return
        self.path.setText(shorten_path(filename))
        self.valueChanged.emit(filename)

    @Slot()
    def handle_edited_path(self):
        self.valueChanged.emit(expand_path(self.path.text()))


class TableOption(QTableWidget):
    def __init__(self):
        super().__init__()
        self.horizontalHeader().setStretchLastSection(False)
        self.setSelectionMode(self.SelectionMode.SingleSelection)
        self.setTabKeyNavigation(False)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.verticalHeader().hide()
        self.currentItemChanged.connect(self._on_current_item_changed)

    def _on_current_item_changed(self, current, previous):
        # Ensure current item is visible.
        parent = self.parent()
        while parent is not None:
            if isinstance(parent, QScrollArea):
                row = current.row()
                pos = self.pos()
                x = pos.x()
                y = +pos.y() + self.rowViewportPosition(row) + self.rowHeight(row)
                parent.ensureVisible(x, y)
                return
            parent = parent.parent()


class KeymapOption(TableOption):
    valueChanged = Signal(object)

    class ItemDelegate(QStyledItemDelegate):
        def __init__(self, action_list):
            super().__init__()
            self._action_list = action_list

        def createEditor(self, parent, option, index):
            if index.column() == 1:
                combo = QComboBox(parent)
                combo.addItem("")
                combo.addItems(self._action_list)
                return combo
            return super().createEditor(parent, option, index)

    def __init__(self):
        super().__init__()
        self._value = []
        self._updating = False
        self.setColumnCount(2)
        self.setHorizontalHeaderLabels(
            (
                # i18n: Widget: “KeymapOption”.
                _("Key"),
                # i18n: Widget: “KeymapOption”.
                _("Action"),
            )
        )
        self.cellChanged.connect(self._on_cell_changed)

    def setValue(self, value):
        self._updating = True
        self._value = copy(value)
        self.setRowCount(0)
        if value is not None:
            row = -1
            for key in value.get_keys():
                action = value.get_action(key)
                if action is None:
                    action = ""
                row += 1
                self.insertRow(row)
                item = QTableWidgetItem(key)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.setItem(row, 0, item)
                item = QTableWidgetItem(action)
                self.setItem(row, 1, item)
        self.resizeColumnsToContents()
        self.setMinimumSize(self.viewportSizeHint())
        self.setItemDelegate(KeymapOption.ItemDelegate(value.get_actions()))
        self._updating = False

    def _on_cell_changed(self, row, column):
        if self._updating:
            return
        key = self.item(row, 0).data(Qt.ItemDataRole.DisplayRole)
        action = self.item(row, 1).data(Qt.ItemDataRole.DisplayRole)
        bindings = self._value.get_bindings()
        if action:
            bindings[key] = action
        else:
            bindings.pop(key, None)
        self._value.set_bindings(bindings)
        self.valueChanged.emit(self._value)


class MultipleChoicesOption(TableOption):
    valueChanged = Signal(object)

    LABELS = (
        # i18n: Widget: “MultipleChoicesOption”.
        _("Selected"),
        # i18n: Widget: “MultipleChoicesOption”.
        _("Choice"),
    )

    # i18n: Widget: “MultipleChoicesOption”.
    def __init__(self, choices=None, labels=None):
        super().__init__()
        if labels is None:
            labels = self.LABELS
        self._value: Set[str] = set()
        self._updating = False
        self._choices = {} if choices is None else choices
        self._reversed_choices = {
            translation: choice for choice, translation in choices.items()
        }
        self.setSizeAdjustPolicy(
            QAbstractScrollArea.SizeAdjustPolicy.AdjustToContentsOnFirstShow
        )
        self.setSizePolicy(
            QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        )
        self.setColumnCount(2)
        self.setHorizontalHeaderLabels(labels)
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        header.setStretchLastSection(True)
        self.cellChanged.connect(self._on_cell_changed)

    def setValue(self, value):
        self._updating = True
        self.setRowCount(0)
        if value is None:
            value = set()
        else:
            # Don't mutate the original value.
            value = set(value)
        self._value = value
        row = -1
        for choice in sorted(self._reversed_choices):
            row += 1
            self.insertRow(row)
            item = QTableWidgetItem()
            item.setFlags(
                (item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                | Qt.ItemFlag.ItemIsUserCheckable
            )
            item.setCheckState(
                Qt.CheckState.Checked if choice in value else Qt.CheckState.Unchecked
            )
            self.setItem(row, 0, item)
            item = QTableWidgetItem(self._choices[choice])
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.setItem(row, 1, item)
        self.resizeColumnsToContents()
        self._updating = False

    def _on_cell_changed(self, row, column):
        if self._updating:
            return
        assert column == 0
        name_item = self.item(row, 1)
        state_item = self.item(row, 0)
        if name_item is None or state_item is None:
            return
        name = name_item.data(Qt.ItemDataRole.DisplayRole)
        if name is None:
            return
        choice = self._reversed_choices.get(name)
        if choice is None:
            return
        if state_item.checkState() == Qt.CheckState.Checked:
            self._value.add(choice)
        else:
            self._value.discard(choice)
        self.valueChanged.emit(self._value)


class BooleanAsDualChoiceOption(ChoiceOption):
    valueChanged = Signal(bool)

    def __init__(self, choice_false, choice_true):
        choices = {False: choice_false, True: choice_true}
        super().__init__(choices)


class TextWrapQLabel(QLabel):
    """Simple QLabel wrapper that enables wordWrap"""

    def __init__(self, *args):
        super().__init__(*args)
        self.setWordWrap(True)


class ConfigOption:
    def __init__(
        self,
        display_name,
        option_name,
        widget_class,
        help_text="",
        dependents=(),
        additional_widget_classes=[],
    ):
        self.display_name = display_name
        self.option_name = option_name
        self.help_text = help_text
        self.widget_class = widget_class
        self.dependents = dependents
        self.layout = None
        self.widget = None
        self.label = None
        # Other widgets to be added immediately after the main widget_class
        # Does not work in dependents
        self.additional_widget_classes = additional_widget_classes


class ConfigWindow(QDialog, Ui_ConfigWindow, WindowStateMixin):
    ROLE = "configuration"

    def __init__(self, engine):
        super().__init__()
        self.setupUi(self)
        self._engine = engine
        machines = {
            plugin.name: _(plugin.name) for plugin in registry.list_plugins("machine")
        }
        mappings = (
            # i18n: Widget: “ConfigWindow”.
            (
                _("Interface"),
                (
                    ConfigOption(
                        _("Appearance:"),
                        "appearance_mode",
                        partial(
                            ChoiceOption,
                            choices={
                                "system": _("System"),
                                "light": _("Light"),
                                "dark": _("Dark"),
                            },
                        ),
                        _(
                            "Set the application appearance:\n"
                            "- System: follow the operating system mode\n"
                            "- Light: force light mode\n"
                            "- Dark: force dark mode"
                        ),
                    ),
                    ConfigOption(
                        _("Start minimized:"),
                        "start_minimized",
                        BooleanOption,
                        _("Minimize the main window to systray on startup."),
                    ),
                    ConfigOption(
                        _("Show paper tape:"),
                        "show_stroke_display",
                        BooleanOption,
                        _("Open the paper tape on startup."),
                    ),
                    ConfigOption(
                        _("Show suggestions:"),
                        "show_suggestions_display",
                        BooleanOption,
                        _("Open the suggestions dialog on startup."),
                    ),
                    ConfigOption(
                        _("Add translation dialog opacity:"),
                        "translation_frame_opacity",
                        partial(IntOption, maximum=100, minimum=0),
                        _(
                            "Set the translation dialog opacity:\n"
                            "- 0 makes the dialog invisible\n"
                            "- 100 is fully opaque"
                        ),
                    ),
                    ConfigOption(
                        _("Dictionaries display order:"),
                        "classic_dictionaries_display_order",
                        partial(
                            BooleanAsDualChoiceOption, _("top-down"), _("bottom-up")
                        ),
                        _(
                            "Set the display order for dictionaries:\n"
                            "- top-down: match the search order; highest priority first\n"
                            "- bottom-up: reverse search order; lowest priority first\n"
                        ),
                    ),
                ),
            ),
            # i18n: Widget: “ConfigWindow”.
            (
                _("Logging"),
                (
                    ConfigOption(
                        _("Log file:"),
                        "log_file_name",
                        partial(
                            FileOption, _("Select a log file"), _("Log files (*.log)")
                        ),
                        _("File to use for logging strokes/translations."),
                    ),
                    ConfigOption(
                        _("Log strokes:"),
                        "enable_stroke_logging",
                        BooleanOption,
                        _("Save strokes to the logfile."),
                    ),
                    ConfigOption(
                        _("Log translations:"),
                        "enable_translation_logging",
                        BooleanOption,
                        _("Save translations to the logfile."),
                    ),
                ),
            ),
            # i18n: Widget: “ConfigWindow”.
            (
                _("Machine"),
                (
                    ConfigOption(
                        _("Machine:"),
                        "machine_type",
                        partial(ChoiceOption, choices=machines),
                        dependents=(
                            ("machine_specific_options", self._update_machine_options),
                            (
                                "system_keymap",
                                lambda v: self._update_keymap(machine_type=v),
                            ),
                        ),
                    ),
                    ConfigOption(
                        _("Options:"), "machine_specific_options", self._machine_option
                    ),
                    ConfigOption(_("Keymap:"), "system_keymap", KeymapOption),
                ),
            ),
            # i18n: Widget: “ConfigWindow”.
            (
                _("Output"),
                (
                    ConfigOption(
                        _("Enable at start:"),
                        "auto_start",
                        BooleanOption,
                        _("Enable output on startup."),
                    ),
                    ConfigOption(
                        _("Start attached:"),
                        "start_attached",
                        BooleanOption,
                        _(
                            "Disable preceding space on first output.\n"
                            "\n"
                            "This option is only applicable when spaces are placed before."
                        ),
                    ),
                    ConfigOption(
                        _("Start capitalized:"),
                        "start_capitalized",
                        BooleanOption,
                        _("Capitalize the first word."),
                    ),
                    ConfigOption(
                        _("Space placement:"),
                        "space_placement",
                        partial(
                            ChoiceOption,
                            choices={
                                "Before Output": _("Before Output"),
                                "After Output": _("After Output"),
                            },
                        ),
                        _("Set automatic space placement: before or after each word."),
                    ),
                    ConfigOption(
                        _("Undo levels:"),
                        "undo_levels",
                        partial(IntOption, maximum=10000, minimum=MINIMUM_UNDO_LEVELS),
                        _(
                            "Set how many preceding strokes can be undone.\n"
                            "\n"
                            "Note: the effective value will take into account the\n"
                            "dictionaries entry with the maximum number of strokes."
                        ),
                    ),
                    ConfigOption(
                        _("Key press delay (ms):"),
                        "time_between_key_presses",
                        partial(
                            IntOption,
                            maximum=100000,
                            minimum=MINIMUM_TIME_BETWEEN_KEY_PRESSES,
                        ),
                        _(
                            "Set the delay between emulated key presses (in milliseconds).\n"
                            "\n"
                            "Some programs may drop key presses if too many are sent\n"
                            "within a short period of time. Increasing the delay gives\n"
                            "programs time to process each key press.\n"
                            "Setting the delay too high will negatively impact the\n"
                            "performance of key stroke output."
                        ),
                    ),
                    ConfigOption(
                        _("Linux keyboard layout:"),
                        "keyboard_layout",
                        partial(
                            ChoiceOption,
                            choices={
                                "qwerty": "qwerty",
                                "qwertz": "qwertz",
                                "colemak": "colemak",
                                "colemak-dh": "colemak-dh",
                                "dvorak": "dvorak",
                                "wayland-auto": "wayland-auto",
                            },
                        ),
                        _(
                            "Set the keyboard layout configured in your system.\n"
                            "This only applies when using Linux/BSD and not using X11.\n\n"
                            "When wayland-auto is selected,"
                            "Plover is only able detect the first keyboard layout\n"
                            "and can not detect to layout switches."
                        ),
                        additional_widget_classes=[
                            partial(
                                TextWrapQLabel,
                                _(
                                    "When wayland-auto is selected, "
                                    "Plover is only able detect the first keyboard layout "
                                    "and can not detect to layout switches."
                                ),
                            )
                        ],
                    ),
                ),
            ),
            # i18n: Widget: “ConfigWindow”.
            (
                _("Plugins"),
                (
                    ConfigOption(
                        _("Extensions:"),
                        "enabled_extensions",
                        partial(
                            MultipleChoicesOption,
                            choices={
                                plugin.name: plugin.name
                                for plugin in registry.list_plugins("extension")
                            },
                            labels=(_("Enabled"), _("Name")),
                        ),
                        _("Configure enabled plugin extensions."),
                    ),
                ),
            ),
            # i18n: Widget: “ConfigWindow”.
            (
                _("System"),
                (
                    ConfigOption(
                        _("System:"),
                        "system_name",
                        partial(
                            ChoiceOption,
                            choices={
                                plugin.name: plugin.name
                                for plugin in registry.list_plugins("system")
                            },
                        ),
                        dependents=(
                            (
                                "system_keymap",
                                lambda v: self._update_keymap(system_name=v),
                            ),
                        ),
                    ),
                ),
            ),
        )
        # Only keep supported options, to avoid messing with things like
        # dictionaries, that are handled by another (possibly concurrent)
        # dialog.
        self._supported_options = set()
        for section, option_list in mappings:
            self._supported_options.update(option.option_name for option in option_list)
        self._load_config()
        # Create and fill tabs.
        option_by_name = {}
        for section, option_list in mappings:
            layout = QFormLayout()
            for option in option_list:
                option_by_name[option.option_name] = option
                option.layout = layout
                option.widget = self._create_option_widget(option)
                option.label = QLabel(option.display_name)
                option.label.setToolTip(option.help_text)
                option.label.setBuddy(option.widget)
                layout.addRow(option.label, option.widget)
                for additional_widget_class in option.additional_widget_classes:
                    layout.addRow(None, additional_widget_class())
            frame = QFrame()
            frame.setLayout(layout)
            frame.setAccessibleName(section)
            frame.setFocusProxy(option_list[0].widget)
            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setWidget(frame)
            scroll_area.setFocusProxy(frame)
            self.tabs.addTab(scroll_area, section)

        # platform specific overwrites
        if PLATFORM == "linux":
            # Appearance overwrite doesn't work on Linux so we're not showing the option
            appearance_option = option_by_name.get("appearance_mode")
            if appearance_option is not None:
                appearance_option.label.hide()
                appearance_option.widget.hide()
        if PLATFORM != "linux":
            # Keyboard layout is only relevant on Linux
            keyboard_layout_option = option_by_name.get("keyboard_layout")
            if keyboard_layout_option is not None:
                keyboard_layout_option.label.hide()
                keyboard_layout_option.widget.hide()

        # temporary hiding start_minimized setting on macOS due to bug in
        # macOS 26, see https://github.com/openstenoproject/plover/issues/1782
        if PLATFORM == "mac":
            start_minimized_option = option_by_name.get("start_minimized")
            if start_minimized_option is not None:
                start_minimized_option.label.hide()
                start_minimized_option.widget.hide()

        # Update dependents.
        for option in option_by_name.values():
            option.dependents = [
                (option_by_name[option_name], update_fn)
                for option_name, update_fn in option.dependents
            ]
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).clicked.connect(
            self.on_apply
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(
            self.on_apply
        )
        self.tabs.currentWidget().setFocus()
        self.restore_state()
        self.finished.connect(self.save_state)

    def _update_appearance(self):
        appearance.update(self._config.maps[0])

    def _save_config(self):
        """Persist the overrides from this dialog back into the engine config.

        This uses the engine's async config update mechanism; the engine thread
        will apply the update after it processes the queued job.
        """
        with self._engine:
            self._engine.config = self._config.maps[0]

    def _load_config(self):
        """Load the current config from the engine into this dialog."""
        with self._engine:
            base_config = {
                name: value
                for name, value in self._engine.config.items()
                if name in self._supported_options
            }
        self._config = ChainMap({}, base_config)

    def _machine_option(self, *args):
        machine_options = {
            plugin.name: plugin.obj
            for plugin in registry.list_plugins("gui.qt.machine_option")
        }
        machine_type = self._config["machine_type"]
        machine_class = registry.get_plugin("machine", machine_type).obj
        for klass in machine_class.mro():
            # Look for `module_name:class_name` before `class_name`.
            for name in (
                "%s:%s" % (klass.__module__, klass.__name__),
                klass.__name__,
            ):
                opt_class = machine_options.get(name)
                if opt_class is not None:
                    return opt_class(*args)
        return NopeOption(*args)

    def _update_machine_options(self, machine_type=None):
        return self._engine[
            ("machine_specific_options", machine_type or self._config["machine_type"])
        ]

    def _update_keymap(self, system_name=None, machine_type=None):
        return self._engine[
            (
                "system_keymap",
                system_name or self._config["system_name"],
                machine_type or self._config["machine_type"],
            )
        ]

    def _create_option_widget(self, option):
        widget = option.widget_class()
        widget.setToolTip(option.help_text)
        widget.setAccessibleName(option.display_name)
        widget.setAccessibleDescription(option.help_text)
        widget.valueChanged.connect(partial(self.on_option_changed, option))
        widget.setValue(self._config[option.option_name])
        return widget

    def keyPressEvent(self, event):
        # Disable Enter/Return key to trigger "OK".
        if event.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return):
            return
        super().keyPressEvent(event)

    def on_option_changed(self, option, value):
        self._config[option.option_name] = value
        for dependent, update_fn in option.dependents:
            # Ensure unsaved changes are discarded.
            if dependent.option_name in self._config.maps[0]:
                del self._config.maps[0][dependent.option_name]
            self._config.maps[1][dependent.option_name] = update_fn(value)
            widget = self._create_option_widget(dependent)
            dependent.layout.replaceWidget(dependent.widget, widget)
            dependent.label.setBuddy(widget)
            dependent.widget.deleteLater()
            dependent.widget = widget

    def on_apply(self):
        self._update_appearance()
        self._save_config()
