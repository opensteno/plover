from evdev import (
    UInput,
    ecodes as e,
    util,
    InputDevice,
    list_devices,
    InputEvent,
    KeyEvent,
)
import threading
import os
import selectors

from psutil import process_iter

from plover.output.keyboard import GenericKeyboardEmulation
from plover.machine.keyboard_capture import Capture
from plover.key_combo import parse_key_combo
from plover import log

# Shared keys between all layouts
BASE_LAYOUT = {
    # Modifiers
    "alt_l": e.KEY_LEFTALT,
    "alt_r": e.KEY_RIGHTALT,
    "alt": e.KEY_LEFTALT,
    "ctrl_l": e.KEY_LEFTCTRL,
    "ctrl_r": e.KEY_RIGHTCTRL,
    "ctrl": e.KEY_LEFTCTRL,
    "control_l": e.KEY_LEFTCTRL,
    "control_r": e.KEY_RIGHTCTRL,
    "control": e.KEY_LEFTCTRL,
    "shift_l": e.KEY_LEFTSHIFT,
    "shift_r": e.KEY_RIGHTSHIFT,
    "shift": e.KEY_LEFTSHIFT,
    "super_l": e.KEY_LEFTMETA,
    "super_r": e.KEY_RIGHTMETA,
    "super": e.KEY_LEFTMETA,
    # Numbers
    "1": e.KEY_1,
    "2": e.KEY_2,
    "3": e.KEY_3,
    "4": e.KEY_4,
    "5": e.KEY_5,
    "6": e.KEY_6,
    "7": e.KEY_7,
    "8": e.KEY_8,
    "9": e.KEY_9,
    "0": e.KEY_0,
    # Symbols
    " ": e.KEY_SPACE,
    "\b": e.KEY_BACKSPACE,
    "\n": e.KEY_ENTER,
    # https://github.com/openstenoproject/plover/blob/9b5a357f1fb57cb0a9a8596ae12cd1e84fcff6c4/plover/oslayer/osx/keyboardcontrol.py#L75
    # https://gist.github.com/jfortin42/68a1fcbf7738a1819eb4b2eef298f4f8
    "return": e.KEY_ENTER,
    "tab": e.KEY_TAB,
    "backspace": e.KEY_BACKSPACE,
    "delete": e.KEY_DELETE,
    "escape": e.KEY_ESC,
    "clear": e.KEY_CLEAR,
    "minus": e.KEY_MINUS,
    "equal": e.KEY_EQUAL,
    "bracketleft": e.KEY_LEFTBRACE,
    "bracketright": e.KEY_RIGHTBRACE,
    "backslash": e.KEY_BACKSLASH,
    "semicolon": e.KEY_SEMICOLON,
    "apostrophe": e.KEY_APOSTROPHE,
    "comma": e.KEY_COMMA,
    "dot": e.KEY_DOT,
    "slash": e.KEY_SLASH,
    "grave": e.KEY_GRAVE,
    "-": e.KEY_MINUS,
    "=": e.KEY_EQUAL,
    "[": e.KEY_LEFTBRACE,
    "]": e.KEY_RIGHTBRACE,
    "\\": e.KEY_BACKSLASH,
    ";": e.KEY_SEMICOLON,
    "'": e.KEY_APOSTROPHE,
    ",": e.KEY_COMMA,
    ".": e.KEY_DOT,
    "/": e.KEY_SLASH,
    "`": e.KEY_GRAVE,
    # Navigation
    "up": e.KEY_UP,
    "down": e.KEY_DOWN,
    "left": e.KEY_LEFT,
    "right": e.KEY_RIGHT,
    "page_up": e.KEY_PAGEUP,
    "page_down": e.KEY_PAGEDOWN,
    "home": e.KEY_HOME,
    "insert": e.KEY_INSERT,
    "end": e.KEY_END,
    "space": e.KEY_SPACE,
    "print": e.KEY_PRINT,
    # Function keys
    "fn": e.KEY_FN,
    "f1": e.KEY_F1,
    "f2": e.KEY_F2,
    "f3": e.KEY_F3,
    "f4": e.KEY_F4,
    "f5": e.KEY_F5,
    "f6": e.KEY_F6,
    "f7": e.KEY_F7,
    "f8": e.KEY_F8,
    "f9": e.KEY_F9,
    "f10": e.KEY_F10,
    "f11": e.KEY_F11,
    "f12": e.KEY_F12,
    "f13": e.KEY_F13,
    "f14": e.KEY_F14,
    "f15": e.KEY_F15,
    "f16": e.KEY_F16,
    "f17": e.KEY_F17,
    "f18": e.KEY_F18,
    "f19": e.KEY_F19,
    "f20": e.KEY_F20,
    "f21": e.KEY_F21,
    "f22": e.KEY_F22,
    "f23": e.KEY_F23,
    "f24": e.KEY_F24,
    # Numpad
    "kp_1": e.KEY_KP1,
    "kp_2": e.KEY_KP2,
    "kp_3": e.KEY_KP3,
    "kp_4": e.KEY_KP4,
    "kp_5": e.KEY_KP5,
    "kp_6": e.KEY_KP6,
    "kp_7": e.KEY_KP7,
    "kp_8": e.KEY_KP8,
    "kp_9": e.KEY_KP9,
    "kp_0": e.KEY_KP0,
    "kp_add": e.KEY_KPPLUS,
    "kp_decimal": e.KEY_KPDOT,
    "kp_delete": e.KEY_DELETE,  # There is no KPDELETE
    "kp_divide": e.KEY_KPSLASH,
    "kp_enter": e.KEY_KPENTER,
    "kp_equal": e.KEY_KPEQUAL,
    "kp_multiply": e.KEY_KPASTERISK,
    "kp_subtract": e.KEY_KPMINUS,
    # Media keys
    "audioraisevolume": e.KEY_VOLUMEUP,
    "audiolowervolume": e.KEY_VOLUMEDOWN,
    "monbrightnessup": e.KEY_BRIGHTNESSUP,
    "monbrightnessdown": e.KEY_BRIGHTNESSDOWN,
    "audiomute": e.KEY_MUTE,
    "num_lock": e.KEY_NUMLOCK,
    "eject": e.KEY_EJECTCD,
    "audiopause": e.KEY_PAUSE,
    "audioplay": e.KEY_PLAY,
    "audionext": e.KEY_NEXT,
    "audiorewind": e.KEY_REWIND,
    "kbdbrightnessup": e.KEY_KBDILLUMUP,
    "kbdbrightnessdown": e.KEY_KBDILLUMDOWN,
}

DEFAULT_LAYOUT = "qwerty"
LAYOUTS = {
    # Only specify keys that differ from qwerty
    "qwerty": {
        **BASE_LAYOUT,
        # Top row
        "q": e.KEY_Q,
        "w": e.KEY_W,
        "e": e.KEY_E,
        "r": e.KEY_R,
        "t": e.KEY_T,
        "y": e.KEY_Y,
        "u": e.KEY_U,
        "i": e.KEY_I,
        "o": e.KEY_O,
        "p": e.KEY_P,
        # Middle row
        "a": e.KEY_A,
        "s": e.KEY_S,
        "d": e.KEY_D,
        "f": e.KEY_F,
        "g": e.KEY_G,
        "h": e.KEY_H,
        "j": e.KEY_J,
        "k": e.KEY_K,
        "l": e.KEY_L,
        # Bottom row
        "z": e.KEY_Z,
        "x": e.KEY_X,
        "c": e.KEY_C,
        "v": e.KEY_V,
        "b": e.KEY_B,
        "n": e.KEY_N,
        "m": e.KEY_M,
    },
    "qwertz": {
        **BASE_LAYOUT,
        # Top row
        "q": e.KEY_Q,
        "w": e.KEY_W,
        "e": e.KEY_E,
        "r": e.KEY_R,
        "t": e.KEY_T,
        "z": e.KEY_Y,
        "u": e.KEY_U,
        "i": e.KEY_I,
        "o": e.KEY_O,
        "p": e.KEY_P,
        # Middle row
        "a": e.KEY_A,
        "s": e.KEY_S,
        "d": e.KEY_D,
        "f": e.KEY_F,
        "g": e.KEY_G,
        "h": e.KEY_H,
        "j": e.KEY_J,
        "k": e.KEY_K,
        "l": e.KEY_L,
        # Bottom row
        "y": e.KEY_Z,
        "x": e.KEY_X,
        "c": e.KEY_C,
        "v": e.KEY_V,
        "b": e.KEY_B,
        "n": e.KEY_N,
        "m": e.KEY_M,
    },
    "colemak": {
        **BASE_LAYOUT,
        # Top row
        "q": e.KEY_Q,
        "w": e.KEY_W,
        "f": e.KEY_E,
        "p": e.KEY_R,
        "g": e.KEY_T,
        "j": e.KEY_Y,
        "l": e.KEY_U,
        "u": e.KEY_I,
        "y": e.KEY_O,
        # Middle row
        "a": e.KEY_A,
        "r": e.KEY_S,
        "s": e.KEY_D,
        "t": e.KEY_F,
        "d": e.KEY_G,
        "h": e.KEY_H,
        "n": e.KEY_J,
        "e": e.KEY_K,
        "i": e.KEY_L,
        "o": e.KEY_SEMICOLON,
        # Bottom row
        "z": e.KEY_Z,
        "x": e.KEY_X,
        "c": e.KEY_C,
        "v": e.KEY_V,
        "b": e.KEY_B,
        "k": e.KEY_N,
        "m": e.KEY_M,
    },
    "colemak-dh": {
        **BASE_LAYOUT,
        # Top row
        "q": e.KEY_Q,
        "w": e.KEY_W,
        "f": e.KEY_E,
        "p": e.KEY_R,
        "b": e.KEY_T,
        "j": e.KEY_Y,
        "l": e.KEY_U,
        "u": e.KEY_I,
        "y": e.KEY_O,
        # Middle row
        "a": e.KEY_A,
        "r": e.KEY_S,
        "s": e.KEY_D,
        "t": e.KEY_F,
        "g": e.KEY_G,
        "m": e.KEY_H,
        "n": e.KEY_J,
        "e": e.KEY_K,
        "i": e.KEY_L,
        "o": e.KEY_SEMICOLON,
        # Bottom row
        "z": e.KEY_BACKSLASH,  # less than-key
        "x": e.KEY_Z,
        "c": e.KEY_X,
        "d": e.KEY_C,
        "v": e.KEY_V,
        "k": e.KEY_N,
        "h": e.KEY_M,
    },
    "dvorak": {
        **BASE_LAYOUT,
        # Top row
        "'": e.KEY_Q,
        ",": e.KEY_W,
        ".": e.KEY_E,
        "p": e.KEY_R,
        "y": e.KEY_T,
        "f": e.KEY_Y,
        "g": e.KEY_U,
        "c": e.KEY_I,
        "r": e.KEY_O,
        "l": e.KEY_P,
        "/": e.KEY_LEFTBRACE,
        "=": e.KEY_RIGHTBRACE,
        # Middle row
        "a": e.KEY_A,
        "o": e.KEY_S,
        "e": e.KEY_D,
        "u": e.KEY_F,
        "i": e.KEY_G,
        "d": e.KEY_H,
        "h": e.KEY_J,
        "t": e.KEY_K,
        "n": e.KEY_L,
        "s": e.KEY_SEMICOLON,
        "-": e.KEY_APOSTROPHE,
        # Bottom row
        ";": e.KEY_Z,
        "q": e.KEY_X,
        "j": e.KEY_C,
        "k": e.KEY_V,
        "x": e.KEY_B,
        "b": e.KEY_N,
        "m": e.KEY_M,
        "w": e.KEY_COMMA,
        "v": e.KEY_DOT,
        "z": e.KEY_SLASH,
    },
}

KEYCODE_TO_KEY = dict(
    zip(LAYOUTS[DEFAULT_LAYOUT].values(), LAYOUTS[DEFAULT_LAYOUT].keys())
)

MODIFIER_KEY_CODES: set[int] = {
    e.KEY_LEFTSHIFT,
    e.KEY_RIGHTSHIFT,
    e.KEY_LEFTCTRL,
    e.KEY_RIGHTCTRL,
    e.KEY_LEFTALT,
    e.KEY_RIGHTALT,
    e.KEY_LEFTMETA,
    e.KEY_RIGHTMETA,
}


def get_available_devices():
    input_devices = [InputDevice(path) for path in list_devices()]
    keyboard_devices = [dev for dev in input_devices if filter_devices(dev)]
    return keyboard_devices


def filter_devices(device):
    """
    Filter out devices that should not be grabbed and suppressed, to avoid output feeding into itself.
    """
    is_uinput = device.name == "py-evdev-uinput" or device.phys == "py-evdev-uinput"
    # Check for some common keys to make sure it's really a keyboard
    keys = device.capabilities().get(e.EV_KEY, [])
    keyboard_keys_present = any(
        key in keys for key in [e.KEY_ESC, e.KEY_SPACE, e.KEY_ENTER, e.KEY_LEFTSHIFT]
    )

    return not is_uinput and keyboard_keys_present


class KeyboardEmulation(GenericKeyboardEmulation):
    def __init__(self):
        super().__init__()
        # Initialize UInput with all keys available
        self._res = util.find_ecodes_by_regex(r"KEY_.*")
        self._ui = UInput(self._res)

        # Check that ibus or fcitx5 is running
        if not any(p.name() in ["ibus-daemon", "fcitx5"] for p in process_iter()):
            log.warning(
                "It appears that an input method, such as ibus or fcitx5, is not running on your system. Without this, some text may not be output correctly."
            )

    def _update_layout(self, layout):
        if layout not in LAYOUTS:
            log.warning(f"Layout {layout} not supported. Falling back to qwerty.")
        self._KEY_TO_KEYCODE = LAYOUTS.get(layout, LAYOUTS[DEFAULT_LAYOUT])

    def _get_key(self, key):
        """Helper function to get the keycode and potential shift key for uppercase."""
        if key in self._KEY_TO_KEYCODE:
            return (self._KEY_TO_KEYCODE[key], [])
        elif key.lower() in self._KEY_TO_KEYCODE:
            # mods is a list for the potential of expanding it in the future to include altgr
            return (
                self._KEY_TO_KEYCODE[key.lower()],
                [self._KEY_TO_KEYCODE["shift_l"]],
            )
        return (None, [])

    def _press_key(self, key, state):
        self._ui.write(e.EV_KEY, key, 1 if state else 0)
        self._ui.syn()

    """
    Send a unicode character.
    This depends on an IME such as iBus or fcitx5. iBus is used by GNOME, and fcitx5 by KDE.
    It assumes the default keybinding ctrl-shift-u, enter hex, enter is used, which is the default in both.
    From my testing, it works fine in using iBus and fcitx5, but in kitty terminal emulator, which uses
    the same keybinding, it's too fast for it to handle and ends up writing random stuff. I don't
    think there is a way to fix that other than increasing the delay.
    """

    def _send_unicode(self, hex):
        self.send_key_combination("ctrl_l(shift(u))")
        self.delay()
        self.send_string(hex)
        self.delay()
        self._send_char(" ")

    def _send_char(self, char):
        (base, mods) = self._get_key(char)

        # Key can be sent with a key combination
        if base is not None:
            for mod in mods:
                self._press_key(mod, True)
            self.delay()
            self._press_key(base, True)
            self._press_key(base, False)
            for mod in mods:
                self._press_key(mod, False)

        # Key press can not be emulated - send unicode symbol instead
        else:
            # Convert to hex and remove leading "0x"
            unicode_hex = hex(ord(char))[2:]
            self._send_unicode(unicode_hex)

    def send_string(self, string):
        for key in self.with_delay(list(string)):
            self._send_char(key)

    def send_backspaces(self, count):
        for _ in range(count):
            self._send_char("\b")

    def send_key_combination(self, combo):
        # https://plover.readthedocs.io/en/latest/api/key_combo.html#module-plover.key_combo
        key_events = parse_key_combo(combo)

        for key, pressed in self.with_delay(key_events):
            (base, _) = self._get_key(key)

            if base is not None:
                self._press_key(base, pressed)
            else:
                log.warning("Key " + key + " is not valid!")


class KeyboardCapture(Capture):
    _selector: selectors.DefaultSelector
    _device_thread: threading.Thread | None
    # Pipes to signal `_run` thread to stop
    _device_thread_read_pipe: int | None
    _device_thread_write_pipe: int | None

    def __init__(self):
        super().__init__()
        self._keyboard_selection = ""
        self._devices = self._get_devices()

        self._selector = selectors.DefaultSelector()
        self._device_thread = None
        self._device_thread_read_pipe = None
        self._device_thread_write_pipe = None

        self._res = util.find_ecodes_by_regex(r"KEY_.*")
        self._ui = UInput(self._res)
        self._suppressed_keys = set()
        # The keycodes from evdev, e.g. e.KEY_A refers to the *physical* a, which corresponds with the qwerty layout.

    def _get_devices(self):
        available_devices = get_available_devices()
        return [
            device
            for device in available_devices
            if self._keyboard_selection == "" or device.name == self._keyboard_selection
        ]

    def _grab_devices(self):
        """Grab all devices, waiting for each device to stop having keys pressed.

        If a device is grabbed when keys are being pressed, the key will
        appear to be always pressed down until the device is ungrabbed and the
        key is pressed again.
        See https://stackoverflow.com/questions/41995349/why-does-ioctlfd-eviocgrab-1-cause-key-spam-sometimes
        There is likely a race condition here between checking active keys and
        actually grabbing the device, but it appears to work fine.
        """
        for device in self._devices:
            if len(device.active_keys()) > 0:
                for _ in device.read_loop():
                    if len(device.active_keys()) == 0:
                        # No keys are pressed. Grab the device
                        break
            device.grab()

    def _ungrab_devices(self):
        """Ungrab all devices. Handles all exceptions when ungrabbing."""
        for device in self._devices:
            try:
                device.ungrab()
            except Exception:
                log.debug("failed to ungrab device", exc_info=True)

    def start(self):
        # Exception handling note: cancel() will eventually be called when the
        # machine reconnect button is pressed or when the machine is changed.
        # Therefore, cancel() does not need to be called in the except block.
        try:
            self._grab_devices()
            self._device_thread_read_pipe, self._device_thread_write_pipe = os.pipe()
            self._selector.register(self._device_thread_read_pipe, selectors.EVENT_READ)
            for device in self._devices:
                self._selector.register(device, selectors.EVENT_READ)

            self._device_thread = threading.Thread(target=self._run)
            self._device_thread.start()
        except Exception:
            self._ungrab_devices()
            self._ui.close()
            raise

    def cancel(self):
        if (
            self._device_thread_read_pipe is None
            or self._device_thread_write_pipe is None
        ):
            # The only way for these pipes to be None is if pipe creation in start() failed
            # In that case, no other code after pipe creation would have run
            # and no cleanup is required
            return
        try:
            # Write some arbitrary data to the pipe to signal the _run thread to stop
            os.write(self._device_thread_write_pipe, b"a")
            if self._device_thread is not None:
                self._device_thread.join()
            self._selector.close()
        except Exception:
            log.debug("error stopping KeyboardCapture", exc_info=True)
        finally:
            os.close(self._device_thread_read_pipe)
            os.close(self._device_thread_write_pipe)

    def suppress(self, suppressed_keys=()):
        """
        UInput is not capable of suppressing only specific keys. To get around this, non-suppressed keys
        are passed through to a UInput device and emulated, while keys in this list get sent to plover.
        It does add a little bit of delay, but that is not noticeable.
        """
        self._suppressed_keys = set(suppressed_keys)

    def set_keyboard_selection(self, keyboard_selection: str):
        self._keyboard_selection = keyboard_selection
        self._devices = self._get_devices()

    def _run(self):
        keys_pressed_with_modifier: set[int] = set()
        down_modifier_keys: set[int] = set()

        def _process_key_event(event: InputEvent) -> tuple[str | None, bool]:
            """
            Processes an InputEvent to determine which key Plover should receive
            and whether the event should be suppressed.
            Considers pressed modifiers and Plover's suppressed keys.
            Returns a tuple of (key_to_send_to_plover, suppress)
            """
            if not self._suppressed_keys:
                # No keys are suppressed
                # Always send to Plover so that it can handle global shortcuts like PLOVER_TOGGLE (PHROLG)
                return KEYCODE_TO_KEY.get(event.code, None), False
            if event.code in MODIFIER_KEY_CODES:
                # Can't use if-else because there is a third case: key_hold
                if event.value == KeyEvent.key_down:
                    down_modifier_keys.add(event.code)
                elif event.value == KeyEvent.key_up:
                    down_modifier_keys.discard(event.code)
                return None, False
            key = KEYCODE_TO_KEY.get(event.code, None)
            if key is None:
                # Key is unhandled. Passthrough
                return None, False
            if event.value == KeyEvent.key_down and down_modifier_keys:
                keys_pressed_with_modifier.add(event.code)
                return None, False
            if (
                event.value == KeyEvent.key_up
                and event.code in keys_pressed_with_modifier
            ):
                # Must pass through key up event if key was pressed with modifier
                # or else it will stay pressed down and start repeating.
                # Must release even if modifier key was released first
                keys_pressed_with_modifier.discard(event.code)
                return None, False
            suppress = key in self._suppressed_keys
            return key, suppress

        try:
            while True:
                for key, events in self._selector.select():
                    if key.fd == self._device_thread_read_pipe:
                        # Stop this thread
                        return
                    assert isinstance(key.fileobj, InputDevice)
                    device: InputDevice = key.fileobj
                    for event in device.read():
                        if event.type == e.EV_KEY:
                            key_to_send_to_plover, suppress = _process_key_event(event)
                            if key_to_send_to_plover is not None:
                                # Always send keys to Plover when no keys suppressed.
                                # This is required for global shortcuts like
                                # Plover toggle (PHROLG) when Plover is disabled.
                                # Note: Must explicitly check key_up or key_down
                                # because there is a third case: key_hold
                                if event.value == KeyEvent.key_down:
                                    self.key_down(key_to_send_to_plover)
                                elif event.value == KeyEvent.key_up:
                                    self.key_up(key_to_send_to_plover)
                            if suppress:
                                # Skip rest of loop to prevent event from
                                # being passed through
                                continue

                        # Passthrough event
                        self._ui.write_event(event)
        except Exception:
            log.error("keyboard capture error", exc_info=True)
        finally:
            # Always ungrab devices to prevent exceptions in the _run loop
            # from causing grabbed input devices to be blocked
            self._ungrab_devices()
            self._ui.close()
