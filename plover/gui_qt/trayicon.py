from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMessageBox, QSystemTrayIcon

from plover import _, __name__ as __software_name__
from plover import log
from plover.oslayer.config import PLATFORM
from plover.machine.base import (
    STATE_INITIALIZING,
    STATE_RUNNING,
)


class TrayIcon(QObject):
    def __init__(self):
        super().__init__()
        self._supported = QSystemTrayIcon.isSystemTrayAvailable()
        self._context_menu = None
        self._enabled = False
        self._trayicon = None
        self._state_icons = {}
        for state in (
            "disconnected",
            "disabled",
            "enabled",
        ):
            icon = QIcon(":resources/state-%s.svg" % state)
            if hasattr(icon, "setIsMask"):
                icon.setIsMask(True)
            self._state_icons[state] = icon
        self._machine = None
        self._machine_state = "disconnected"
        self._is_running = False
        self._update_state()

    def set_menu(self, menu):
        self._context_menu = menu
        if self._enabled:
            self._trayicon.setContextMenu(menu)

    def show_message(
        self, message, icon=QSystemTrayIcon.MessageIcon.Information, timeout=10000
    ):
        self._trayicon.showMessage(
            __software_name__.capitalize(), message, icon, timeout
        )

    def log(self, level, message):
        if self._enabled:
            if level <= log.INFO:
                icon = QSystemTrayIcon.MessageIcon.Information
                timeout = 10
            elif level <= log.WARNING:
                icon = QSystemTrayIcon.MessageIcon.Warning
                timeout = 15
            else:
                icon = QSystemTrayIcon.MessageIcon.Critical
                timeout = 25
            self.show_message(message, icon, timeout * 1000)
        else:
            if level <= log.INFO:
                icon = QMessageBox.Information
            elif level <= log.WARNING:
                icon = QMessageBox.Warning
            else:
                icon = QMessageBox.Critical
            msgbox = QMessageBox()
            msgbox.setText(message)
            msgbox.setIcon(icon)
            msgbox.exec()

    def is_supported(self):
        return self._supported

    def enable(self):
        if not self._supported:
            return
        self._trayicon = QSystemTrayIcon()
        # On OS X, the context menu is activated with either mouse buttons,
        # and activation messages are still sent, so ignore those...
        if PLATFORM != "mac":
            self._trayicon.activated.connect(self._on_activated)
        if self._context_menu is not None:
            self._trayicon.setContextMenu(self._context_menu)
        self._enabled = True
        self._update_state()
        self._trayicon.show()

    def disable(self):
        if not self._enabled:
            return
        self._trayicon.hide()
        self._trayicon = None
        self._enabled = False

    def is_enabled(self):
        return self._enabled

    def update_machine_state(self, machine, state):
        self._machine = machine
        self._machine_state = state
        self._update_state()

    def update_output(self, enabled):
        self._is_running = enabled
        self._update_state()

    clicked = Signal()

    def _update_state(self):
        if self._machine_state not in (STATE_INITIALIZING, STATE_RUNNING):
            state = "disconnected"
        else:
            state = "enabled" if self._is_running else "disabled"
        icon = self._state_icons[state]
        if not self._enabled:
            return
        machine_state = _("{machine} is {state}").format(
            machine=_(self._machine),
            state=_(self._machine_state),
        )
        if self._is_running:
            # i18n: Tray icon tooltip.
            output_state = _("output is enabled")
        else:
            # i18n: Tray icon tooltip.
            output_state = _("output is disabled")
        self._trayicon.setIcon(icon)
        self._trayicon.setToolTip(
            # i18n: Tray icon tooltip.
            "Plover:\n- %s\n- %s" % (output_state, machine_state)
        )

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.clicked.emit()
