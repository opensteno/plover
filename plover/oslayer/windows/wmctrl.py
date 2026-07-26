from ctypes import windll, wintypes

GetForegroundWindow = windll.user32.GetForegroundWindow
GetForegroundWindow.argtypes = []
GetForegroundWindow.restype = wintypes.HWND

SetForegroundWindow = windll.user32.SetForegroundWindow
SetForegroundWindow.argtypes = [
    wintypes.HWND,  # hWnd
]
SetForegroundWindow.restype = wintypes.BOOL
