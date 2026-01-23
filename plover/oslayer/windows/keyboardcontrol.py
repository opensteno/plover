# Copyright (c) 2011 Hesky Fisher.
# See LICENSE.txt for details.
#
# winkeyboardcontrol.py - capturing and injecting keyboard events in windows.

"""Keyboard capture and control in windows.

This module provides an interface for basic keyboard event capture and
emulation. Set the key_up and key_down functions of the
KeyboardCapture class to capture keyboard input. Call the send_string
and send_backspaces functions of the KeyboardEmulation class to
emulate keyboard input.

"""

from ctypes import windll, wintypes
import atexit
import ctypes
import multiprocessing
import os
import signal
import threading
import winreg

from plover import log
from plover.key_combo import parse_key_combo
from plover.machine.keyboard_capture import Capture
from plover.misc import to_surrogate_pair
from plover.output.keyboard import GenericKeyboardEmulation

from .keyboardlayout import KeyboardLayout

# For the purposes of this class, we'll only report key presses that
# result in these outputs in order to exclude special key combos.
SCANCODE_TO_KEY = {
    59: "F1",
    60: "F2",
    61: "F3",
    62: "F4",
    63: "F5",
    64: "F6",
    65: "F7",
    66: "F8",
    67: "F9",
    68: "F10",
    87: "F11",
    88: "F12",
    41: "`",
    2: "1",
    3: "2",
    4: "3",
    5: "4",
    6: "5",
    7: "6",
    8: "7",
    9: "8",
    10: "9",
    11: "0",
    12: "-",
    13: "=",
    16: "q",
    17: "w",
    18: "e",
    19: "r",
    20: "t",
    21: "y",
    22: "u",
    23: "i",
    24: "o",
    25: "p",
    26: "[",
    27: "]",
    43: "\\",
    30: "a",
    31: "s",
    32: "d",
    33: "f",
    34: "g",
    35: "h",
    36: "j",
    37: "k",
    38: "l",
    39: ";",
    40: "'",
    44: "z",
    45: "x",
    46: "c",
    47: "v",
    48: "b",
    49: "n",
    50: "m",
    51: ",",
    52: ".",
    53: "/",
    57: "space",
    14: "BackSpace",
    83: "Delete",
    80: "Down",
    79: "End",
    1: "Escape",
    71: "Home",
    82: "Insert",
    75: "Left",
    73: "Page_Up",
    81: "Page_Down",
    28: "Return",
    77: "Right",
    15: "Tab",
    72: "Up",
}

KEY_TO_SCANCODE = dict(zip(SCANCODE_TO_KEY.values(), SCANCODE_TO_KEY.keys()))

PASSTHROUGH_KEYS = {
    0xA2,  # Control
    0xA3,  # Control
    0xA0,  # Shift
    0xA1,  # Shift
    0xA4,  # Alt
    0xA5,  # Alt
    0x5B,  # Win
    0x5C,  # Win
}


"""
SendInput code and classes based off:
http://stackoverflow.com/questions/11906925/python-simulate-keydown
"""


class MOUSEINPUT(ctypes.Structure):
    _fields_ = (
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", wintypes.PULONG),
    )


class KEYBDINPUT(ctypes.Structure):
    _fields_ = (
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", wintypes.PULONG),
    )


class _INPUTunion(ctypes.Union):
    _fields_ = (("mi", MOUSEINPUT), ("ki", KEYBDINPUT))


class INPUT(ctypes.Structure):
    _fields_ = (("type", wintypes.DWORD), ("union", _INPUTunion))


SendInput = windll.user32.SendInput
SendInput.argtypes = [
    wintypes.UINT,  # cInputs
    ctypes.POINTER(INPUT),  # pInputs,
    ctypes.c_int,  # cbSize
]
SendInput.restype = wintypes.UINT

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
KEYEVENTF_UNICODE = 0x0004

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1

KF_EXTENDED = 0x0100
LLKHF_EXTENDED = KF_EXTENDED >> 8
LLKHF_LOWER_IL_INJECTED = 0x0002
LLKHF_INJECTED = 0x0010


# Process utils code code based on psutil implementation.

OpenProcess = windll.kernel32.OpenProcess
OpenProcess.argtypes = [
    wintypes.DWORD,  # dwDesiredAccess
    wintypes.BOOL,  # bInheritHandle
    wintypes.DWORD,  # dwProcessId
]
OpenProcess.restype = wintypes.HANDLE

GetExitCodeProcess = windll.kernel32.GetExitCodeProcess
GetExitCodeProcess.argtypes = [
    wintypes.HANDLE,  # hProcess
    wintypes.LPDWORD,  # lpExitCode
]
GetExitCodeProcess.restype = wintypes.BOOL

CloseHandle = windll.kernel32.CloseHandle
CloseHandle.argtypes = [
    wintypes.HANDLE,  # hObject
]
CloseHandle.restype = wintypes.BOOL

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
ERROR_INVALID_PARAMETER = 87
ERROR_ACCESS_DENIED = 5
STILL_ACTIVE = 0x00000103


def pid_exists(pid):
    """Check whether pid exists in the current process table."""

    process = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, 0, pid)
    if not process:
        err = ctypes.GetLastError()
        if err == ERROR_INVALID_PARAMETER:
            # Invalid parameter is no such process.
            return False
        if err == ERROR_ACCESS_DENIED:
            # Access denied obviously means there's a process to deny access to...
            return True
        raise ctypes.WinError(err)

    try:
        exitcode = wintypes.DWORD()
        out = GetExitCodeProcess(process, ctypes.byref(exitcode))
        if not out:
            err = ctypes.GetLastError()
            if err == ERROR_ACCESS_DENIED:
                # Access denied means there's a process
                # there so we'll assume it's running.
                return True
            raise ctypes.WinError(err)

        return exitcode.value == STILL_ACTIVE

    finally:
        CloseHandle(process)


class HeartBeat(threading.Thread):
    def __init__(self, ppid, exitcb):
        super().__init__()
        self._ppid = ppid
        self._exitcb = exitcb
        self._finished = threading.Event()

    def run(self):
        while pid_exists(self._ppid):
            if self._finished.wait(1):
                break
        self._exitcb()

    def stop(self):
        self._finished.set()
        self.join()


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = (
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    )


PKBDLLHOOKSTRUCT = ctypes.POINTER(KBDLLHOOKSTRUCT)
LRESULT = ctypes.c_long
HOOKPROC = ctypes.CFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

SetWindowsHookExA = windll.user32.SetWindowsHookExA
SetWindowsHookExA.argtypes = (
    ctypes.c_int,  # idHook,
    HOOKPROC,  # lpfn,
    wintypes.HINSTANCE,  # hmod,
    wintypes.DWORD,  # dwThreadId
)
SetWindowsHookExA.restype = wintypes.HHOOK

CallNextHookEx = windll.user32.CallNextHookEx
CallNextHookEx.argtypes = (
    wintypes.HHOOK,  # hhk
    ctypes.c_int,  # nCode
    wintypes.WPARAM,  # wParam
    wintypes.LPARAM,  # lParam
)
CallNextHookEx.restype = LRESULT

UnhookWindowsHookEx = windll.user32.UnhookWindowsHookEx
UnhookWindowsHookEx.argtypes = (wintypes.HHOOK,)
UnhookWindowsHookEx.restype = wintypes.BOOL

GetMessageW = windll.user32.GetMessageW
GetMessageW.argtypes = (
    wintypes.LPMSG,  # lpMsg,
    wintypes.HWND,  # hWnd,
    wintypes.UINT,  # wMsgFilterMin,
    wintypes.UINT,  # wMsgFilterMax
)
GetMessageW.restype = wintypes.BOOL

TranslateMessage = windll.user32.TranslateMessage
TranslateMessage.argtypes = (wintypes.MSG,)
TranslateMessage.restype = wintypes.BOOL

DispatchMessageW = windll.user32.DispatchMessageW
DispatchMessageW.argtypes = (wintypes.MSG,)
DispatchMessageW.restype = LRESULT

PostThreadMessageW = windll.user32.PostThreadMessageW
PostThreadMessageW.argtypes = (
    wintypes.DWORD,  # idThread
    wintypes.UINT,  # Msg
    wintypes.WPARAM,  # wParam
    wintypes.LPARAM,  # lParam
)
PostThreadMessageW.restype = wintypes.BOOL

WM_QUIT = 0x12

# Registry setting for low level hook timeout.
REG_LLHOOK_KEY_FULL_NAME = (
    r"HKEY_CURRENT_USER\Control Panel\Desktop\LowLevelHooksTimeout"
)
REG_LLHOOK_KEY_VALUE_NAME = "LowLevelHooksTimeout"
REG_LLHOOK_KEY_VALUE_TYPE = winreg.REG_DWORD
REG_LLHOOK_KEY_VALUE = 5000


class KeyboardCaptureProcess(multiprocessing.Process):
    def __init__(self):
        super().__init__()
        self.daemon = True
        self._ppid = os.getpid()
        self._update_registry()
        self._tid = None
        self._queue = multiprocessing.Queue()
        self._suppressed_keys_bitmask = multiprocessing.Array(
            ctypes.c_uint64, (max(SCANCODE_TO_KEY.keys()) + 63) // 64
        )
        self._suppressed_keys_bitmask[:] = (0xFFFFFFFFFFFFFFFF,) * len(
            self._suppressed_keys_bitmask
        )

    @staticmethod
    def _update_registry():
        # From MSDN documentation:
        #
        # The hook procedure should process a message in less time than the
        # data entry specified in the LowLevelHooksTimeout value in the
        # following registry key:
        #
        # HKEY_CURRENT_USER\Control Panel\Desktop
        #
        # The value is in milliseconds. If the hook procedure times out, the
        # system passes the message to the next hook. However, on Windows 7 and
        # later, the hook is silently removed without being called. There is no
        # way for the application to know whether the hook is removed.

        def _open_key(rights):
            return winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop", 0, rights
            )

        read_key = _open_key(winreg.KEY_READ)
        try:
            value, value_type = winreg.QueryValueEx(read_key, REG_LLHOOK_KEY_VALUE_NAME)
        except OSError:
            value, value_type = (None, None)

        if value_type != REG_LLHOOK_KEY_VALUE_TYPE or value != REG_LLHOOK_KEY_VALUE:
            try:
                write_key = _open_key(winreg.KEY_WRITE)
                winreg.SetValueEx(
                    write_key,
                    REG_LLHOOK_KEY_VALUE_NAME,
                    0,
                    REG_LLHOOK_KEY_VALUE_TYPE,
                    REG_LLHOOK_KEY_VALUE,
                )
            except OSError:
                log.warning(
                    "could not update registry key: %s, see documentation",
                    REG_LLHOOK_KEY_FULL_NAME,
                )
            else:
                log.warning(
                    "the following registry key has been updated, "
                    "you should reboot: %s",
                    REG_LLHOOK_KEY_FULL_NAME,
                )

    def run(self):
        heartbeat = HeartBeat(self._ppid, self._send_quit)
        heartbeat.start()
        try:
            self._run()
        finally:
            heartbeat.stop()

    def _run(self):
        # Ignore KeyboardInterrupt when attached to a console...
        signal.signal(signal.SIGINT, signal.SIG_IGN)

        self._tid = windll.kernel32.GetCurrentThreadId()
        self._queue.put(self._tid)

        passthrough_down_keys = set()

        def on_key(pressed, event):
            if event.flags & LLKHF_EXTENDED:
                return False

            if event.flags & LLKHF_INJECTED:
                # Ignore simulated events (e.g. from KeyboardEmulation).
                return False
            if event.vkCode in PASSTHROUGH_KEYS:
                if pressed:
                    passthrough_down_keys.add(event.vkCode)
                else:
                    passthrough_down_keys.discard(event.vkCode)
            key = SCANCODE_TO_KEY.get(event.scanCode)
            if key is None:
                # Unhandled, ignore and don't suppress.
                return False
            suppressed = bool(
                self._suppressed_keys_bitmask[event.scanCode // 64]
                & (1 << (event.scanCode % 64))
            )
            if pressed and passthrough_down_keys:
                # Modifier(s) pressed, ignore.
                return False
            self._queue.put((None, key, pressed))
            return suppressed

        hook_id = None

        def low_level_handler(code, wparam, lparam):
            if code >= 0:
                event = ctypes.cast(lparam, PKBDLLHOOKSTRUCT)[0]
                pressed = wparam in (0x100, 0x104)
                if on_key(pressed, event):
                    # Suppressed...
                    return 1
            return CallNextHookEx(hook_id, code, wparam, lparam)

        hook_proc = HOOKPROC(low_level_handler)
        hook_id = SetWindowsHookExA(0xD, hook_proc, None, 0)
        if not hook_id:
            self._queue.put(
                (
                    ("failed to install keyboard hook: %s", ctypes.FormatError()),
                    None,
                    None,
                )
            )
            return
        atexit.register(UnhookWindowsHookEx, hook_id)
        msg = wintypes.MSG()
        msg_p = ctypes.byref(msg)
        while GetMessageW(msg_p, None, 0, 0):
            TranslateMessage(msg_p)
            DispatchMessageW(msg_p)

    def _send_quit(self):
        PostThreadMessageW(self._tid, WM_QUIT, 0, 0)

    def start(self):
        self.daemon = True
        super().start()
        self._tid = self._queue.get()

    def stop(self):
        if self.is_alive():
            self._send_quit()
            self.join()
        # Wake up capture thread, so it gets a chance to check if it must stop.
        self._queue.put((None, None, None))

    def suppress(self, suppressed_keys):
        bitmask = [0] * len(self._suppressed_keys_bitmask)
        for key in suppressed_keys:
            code = KEY_TO_SCANCODE[key]
            bitmask[code // 64] |= 1 << (code % 64)
        self._suppressed_keys_bitmask[:] = bitmask

    def get(self):
        return self._queue.get()


class KeyboardCapture(Capture):
    def __init__(self):
        super().__init__()
        self._suppressed_keys = set()
        self._finished = None
        self._thread = None
        self._proc = None

    def start(self):
        self._finished = threading.Event()
        self._proc = KeyboardCaptureProcess()
        self._proc.start()
        self._thread = threading.Thread(target=self._run)
        self._thread.start()

    def _run(self):
        while True:
            error, key, pressed = self._proc.get()
            if error is not None:
                log.error(*error)
            if self._finished.is_set():
                break
            (self.key_down if pressed else self.key_up)(key)

    def cancel(self):
        if self._finished is not None:
            self._finished.set()
        if self._proc is not None:
            self._proc.stop()
        if self._thread is not None:
            self._thread.join()

    def suppress(self, suppressed_keys=()):
        self._suppressed_keys = set(suppressed_keys)
        self._proc.suppress(self._suppressed_keys)


class KeyboardEmulation(GenericKeyboardEmulation):
    def __init__(self):
        super().__init__()
        self.keyboard_layout = KeyboardLayout()

    # Sends input types to buffer
    @staticmethod
    def _send_input(*inputs):
        len_inputs = len(inputs)
        len_pinput = INPUT * len_inputs
        pinputs = len_pinput(*inputs)
        c_size = ctypes.c_int(ctypes.sizeof(INPUT))
        return SendInput(len_inputs, pinputs, c_size)

    # Input type (can be mouse, keyboard)
    @staticmethod
    def _input(structure):
        if isinstance(structure, MOUSEINPUT):
            return INPUT(INPUT_MOUSE, _INPUTunion(mi=structure))
        if isinstance(structure, KEYBDINPUT):
            return INPUT(INPUT_KEYBOARD, _INPUTunion(ki=structure))
        raise TypeError("Cannot create INPUT structure!")

    # Container to send mouse input
    # Not used, but maybe one day it will be useful
    @staticmethod
    def _mouse_input(flags, x, y, data):
        return MOUSEINPUT(x, y, data, flags, 0, None)

    # Keyboard input type to send key input
    @staticmethod
    def _keyboard_input(code, flags):
        if flags & KEYEVENTF_UNICODE:
            # special handling of Unicode characters
            return KEYBDINPUT(0, code, flags, 0, None)
        return KEYBDINPUT(code, 0, flags, 0, None)

    # Abstraction to set flags to 0 and create an input type
    def _keyboard(self, code, flags=0):
        return self._input(self._keyboard_input(code, flags))

    def _key_event(self, keycode, pressed):
        flags = 0 if pressed else KEYEVENTF_KEYUP
        self._send_input(self._keyboard(keycode, flags))

    # Press and release a key
    def _key_press(self, char):
        vk, ss = self.keyboard_layout.char_to_vk_ss[char]
        keycode_list = []
        keycode_list.extend(self.keyboard_layout.ss_to_vks[ss])
        keycode_list.append(vk)
        # Press all keys.
        for keycode in keycode_list:
            self._key_event(keycode, True)
        # Release all keys
        for keycode in keycode_list:
            self._key_event(keycode, False)

    def _refresh_keyboard_layout(self):
        layout_id = KeyboardLayout.current_layout_id()
        if layout_id != self.keyboard_layout.layout_id:
            self.keyboard_layout = KeyboardLayout(layout_id)

    def _key_unicode(self, char):
        pairs = to_surrogate_pair(char)
        # Send press events for all codes, then release events for all codes.
        inputs = [
            self._keyboard(code, KEYEVENTF_UNICODE | direction)
            for direction in (0, KEYEVENTF_KEYUP)
            for code in pairs
        ]
        self._send_input(*inputs)

    def send_backspaces(self, count):
        for _ in self.with_delay(range(count)):
            self._key_press("\x08")

    def send_string(self, string):
        self._refresh_keyboard_layout()
        for char in self.with_delay(string):
            if char in self.keyboard_layout.char_to_vk_ss:
                # We know how to simulate the character.
                self._key_press(char)
            else:
                # Otherwise, we send it as a Unicode string.
                self._key_unicode(char)

    def send_key_combination(self, combo):
        # Make sure keyboard layout is up-to-date.
        self._refresh_keyboard_layout()
        # Parse and validate combo.
        key_events = parse_key_combo(combo, self.keyboard_layout.keyname_to_vk.get)
        # Send events...
        for keycode, pressed in self.with_delay(key_events):
            self._key_event(keycode, pressed)
