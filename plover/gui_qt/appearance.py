from typing import Optional
from plover import log

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication

MODE_SYSTEM = "system"
MODE_LIGHT = "light"
MODE_DARK = "dark"


def _set_mode(mode: Optional[str]) -> None:
    """Apply the requested mode to the current Qt application.

    This function tweaks Qt's idea of the platform color scheme via
    QStyleHints.setColorScheme / unsetColorScheme so that other code can
    query styleHints().colorScheme() and get the effective setting.

    - "system": follow the operating system setting again
    - "light":  force a light color scheme
    - "dark":   force a dark color scheme
    - None:     no-op
    """

    if mode is None:
        # Explicitly do nothing when no mode was provided.
        return

    app = QGuiApplication.instance()
    if not isinstance(app, QGuiApplication):
        # No GUI application instance (or unexpected type); nothing to do.
        return

    # Ensure the style is initialized.
    hints = app.styleHints()

    if mode == MODE_SYSTEM:
        # Remove any explicit override so Qt follows the OS again.
        hints.unsetColorScheme()
    elif mode == MODE_LIGHT:
        hints.setColorScheme(Qt.ColorScheme.Light)
    elif mode == MODE_DARK:
        hints.setColorScheme(Qt.ColorScheme.Dark)
    else:
        log.warning(f"invalid mode config value: {mode}")


def update(config):
    _set_mode(config.get("appearance_mode"))
