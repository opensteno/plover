from .display_server import DISPLAY_SERVER


def GetForegroundWindow():
    return None


def SetForegroundWindow(w):
    pass


if DISPLAY_SERVER == "x11":
    from .wmctrl_x11 import WmCtrl

    _wmctrl = WmCtrl()
    GetForegroundWindow = _wmctrl.get_foreground_window
    SetForegroundWindow = _wmctrl.set_foreground_window
