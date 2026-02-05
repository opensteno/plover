from copy import copy
from pathlib import Path

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import (
    QIntValidator,
    QTextCharFormat,
    QTextFrameFormat,
    QTextListFormat,
    QTextCursor,
    QTextDocument,
)
from PySide6.QtWidgets import (
    QGroupBox,
    QStyle,
    QStyledItemDelegate,
    QToolTip,
)

from serial import Serial
from serial.tools.list_ports import comports

from plover import _
from plover.oslayer.serial import patch_ports_info

from plover.gui_qt.config_keyboard_widget_ui import Ui_KeyboardWidget
from plover.gui_qt.config_serial_widget_ui import Ui_SerialWidget
from plover.gui_qt.config_plover_hid_widget_ui import Ui_PloverHidWidget


def serial_port_details(port_info):
    parts = []
    global_ignore = {None, "n/a", Path(port_info.device).name}
    local_ignore = set(global_ignore)
    for attr, fmt in (
        ("product", _("product: {value}")),
        ("manufacturer", _("manufacturer: {value}")),
        ("serial_number", _("serial number: {value}")),
    ):
        value = getattr(port_info, attr)
        if value not in global_ignore:
            parts.append(fmt.format(value=value))
            local_ignore.add(value)
    description = getattr(port_info, "description")
    if description not in local_ignore:
        parts.insert(0, _("description: {value}").format(value=description))
    if not parts:
        return None
    return parts


class SerialOption(QGroupBox, Ui_SerialWidget):
    class PortDelegate(QStyledItemDelegate):
        def __init__(self):
            super().__init__()
            self._doc = QTextDocument()
            doc_margin = self._doc.documentMargin()
            self._doc.setIndentWidth(doc_margin * 3)
            background = QToolTip.palette().toolTipBase()
            foreground = QToolTip.palette().toolTipText()
            self._device_format = QTextCharFormat()
            self._details_char_format = QTextCharFormat()
            self._details_char_format.setFont(QToolTip.font())
            self._details_char_format.setBackground(background)
            self._details_char_format.setForeground(foreground)
            self._details_frame_format = QTextFrameFormat()
            self._details_frame_format.setBackground(background)
            self._details_frame_format.setForeground(foreground)
            self._details_frame_format.setTopMargin(doc_margin)
            self._details_frame_format.setBottomMargin(-3 * doc_margin)
            self._details_frame_format.setBorderStyle(
                QTextFrameFormat.BorderStyle.BorderStyle_Solid
            )
            self._details_frame_format.setBorder(doc_margin / 2)
            self._details_frame_format.setPadding(doc_margin)
            self._details_list_format = QTextListFormat()
            self._details_list_format.setStyle(QTextListFormat.Style.ListSquare)

        def _format_port(self, index):
            self._doc.clear()
            cursor = QTextCursor(self._doc)
            cursor.setCharFormat(self._device_format)
            port_info = index.data(Qt.ItemDataRole.UserRole)
            if port_info is None:
                cursor.insertText(index.data(Qt.ItemDataRole.DisplayRole))
                return
            cursor.insertText(port_info.device)
            details = serial_port_details(port_info)
            if not details:
                return
            cursor.insertFrame(self._details_frame_format)
            for n, part in enumerate(details):
                if n:
                    cursor.insertBlock()
                cursor.insertText(part, self._details_char_format)

        def paint(self, painter, option, index):
            painter.save()
            if option.state & QStyle.StateFlag.State_Selected:
                painter.fillRect(option.rect, option.palette.highlight())
                text_color = option.palette.highlightedText()
            else:
                text_color = option.palette.text()
            self._device_format.setForeground(text_color)
            doc_margin = self._doc.documentMargin()
            self._details_frame_format.setWidth(option.rect.width() - doc_margin * 2)
            self._format_port(index)
            painter.translate(option.rect.topLeft())
            self._doc.drawContents(painter)
            painter.restore()

        def sizeHint(self, option, index):
            self._format_port(index)
            return self._doc.size().toSize()

    valueChanged = Signal(object)

    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.port.setItemDelegate(self.PortDelegate())
        self._value = {}

    def setValue(self, value):
        self._value = copy(value)
        self.scan()
        port = value["port"]
        if port is not None and port != "None":
            port_index = self.port.findText(port)
            if port_index != -1:
                self.port.setCurrentIndex(port_index)
            else:
                self.port.setCurrentText(port)
        self.baudrate.addItems(map(str, Serial.BAUDRATES))
        self.baudrate.setCurrentText(str(value["baudrate"]))
        self.bytesize.addItems(map(str, Serial.BYTESIZES))
        self.bytesize.setCurrentText(str(value["bytesize"]))
        self.parity.addItems(Serial.PARITIES)
        self.parity.setCurrentText(value["parity"])
        self.stopbits.addItems(map(str, Serial.STOPBITS))
        self.stopbits.setCurrentText(str(value["stopbits"]))
        self.timeout.setValue(value["timeout"])
        for setting in ("xonxoff", "rtscts"):
            widget = getattr(self, setting)
            if setting in value:
                widget.setChecked(value[setting])
            else:
                widget.setEnabled(False)

    def _update(self, field, value):
        self._value[field] = value
        self.valueChanged.emit(self._value)

    def scan(self):
        self.port.clear()
        for port_info in sorted(patch_ports_info(comports())):
            self.port.addItem(port_info.device, port_info)

    @Slot(str)
    def update_port(self, value):
        self._update("port", value)

    @Slot(str)
    def update_baudrate(self, value):
        self._update("baudrate", int(value))

    @Slot(str)
    def update_bytesize(self, value):
        self._update("baudrate", int(value))

    @Slot(str)
    def update_parity(self, value):
        self._update("parity", value)

    def update_stopbits(self, value):
        self._update("stopbits", float(value))

    @Slot(float)
    def update_timeout(self, value):
        self._update("timeout", value)

    @Slot(bool)
    def update_xonxoff(self, value):
        self._update("xonxoff", value)

    @Slot(bool)
    def update_rtscts(self, value):
        self._update("rtscts", value)


class KeyboardOption(QGroupBox, Ui_KeyboardWidget):
    valueChanged = Signal(object)

    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.arpeggiate.setToolTip(
            _(
                "Arpeggiate allows using non-NKRO keyboards.\n"
                "\n"
                "Each key can be pressed separately and the\n"
                "space bar is pressed to send the stroke."
            )
        )
        self._value = {}

    def setValue(self, value):
        self._value = copy(value)
        self.arpeggiate.setChecked(value["arpeggiate"])
        self.first_up_chord_send.setChecked(value["first_up_chord_send"])

    @Slot(bool)
    def update_arpeggiate(self, value):
        self._value["arpeggiate"] = value
        self.valueChanged.emit(self._value)

    @Slot(bool)
    def update_first_up_chord_send(self, value):
        self._value["first_up_chord_send"] = value
        self.valueChanged.emit(self._value)


class PloverHidOption(QGroupBox, Ui_PloverHidWidget):
    valueChanged = Signal(object)

    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self._value = {}
        self.repeat_delay_ms.setValidator(QIntValidator(10, 10000, self))
        self.repeat_interval_ms.setValidator(QIntValidator(10, 10000, self))
        self.device_scan_interval_ms.setValidator(QIntValidator(250, 100000, self))

    def setValue(self, value):
        self._value = copy(value)
        self.first_up_chord_send.setChecked(value["first_up_chord_send"])
        self.double_tap_repeat.setChecked(value["double_tap_repeat"])
        self.repeat_delay_ms.setText(str(value["repeat_delay_ms"]))
        self.repeat_interval_ms.setText(str(value["repeat_interval_ms"]))
        self.device_scan_interval_ms.setText(
            str(value.get("device_scan_interval_ms", 1000))
        )

    @Slot(bool)
    def update_first_up_chord_send(self, value):
        self._value["first_up_chord_send"] = value
        self.valueChanged.emit(self._value)

    @Slot(bool)
    def update_double_tap_repeat(self, value):
        self._value["double_tap_repeat"] = value
        self.valueChanged.emit(self._value)

    @Slot(str)
    def update_repeat_delay_ms(self, text):
        if text.isdigit():
            self._value["repeat_delay_ms"] = int(text)
            self.valueChanged.emit(self._value)

    @Slot(str)
    def update_repeat_interval_ms(self, text):
        if text.isdigit():
            self._value["repeat_interval_ms"] = int(text)
            self.valueChanged.emit(self._value)

    @Slot(str)
    def update_device_scan_interval_ms(self, text):
        if text.isdigit():
            self._value["device_scan_interval_ms"] = int(text)
            self.valueChanged.emit(self._value)
