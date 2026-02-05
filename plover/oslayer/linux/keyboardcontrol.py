from .display_server import DISPLAY_SERVER

if DISPLAY_SERVER == "x11":
    from .keyboardcontrol_x11 import KeyboardCapture, KeyboardEmulation
else:
    from .keyboardcontrol_uinput import KeyboardCapture, KeyboardEmulation

__all__ = ["KeyboardCapture", "KeyboardEmulation"]
