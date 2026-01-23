# coding: utf-8

import threading
from time import sleep
from queue import Queue

from Quartz import (
    CFMachPortCreateRunLoopSource,
    CFMachPortInvalidate,
    CFRunLoopAddSource,
    CFRunLoopSourceInvalidate,
    CFRunLoopGetCurrent,
    CFRunLoopRun,
    CFRunLoopStop,
    CFRelease,
    CGEventCreateKeyboardEvent,
    CGEventGetFlags,
    CGEventGetIntegerValueField,
    CGEventKeyboardSetUnicodeString,
    CGEventMaskBit,
    CGEventPost,
    CGEventSetFlags,
    CGEventSourceCreate,
    CGEventTapCreate,
    CGEventTapEnable,
    kCFRunLoopCommonModes,
    kCGEventFlagMaskAlternate,
    kCGEventFlagMaskCommand,
    kCGEventFlagMaskControl,
    kCGEventFlagMaskNonCoalesced,
    kCGEventFlagMaskNumericPad,
    kCGEventFlagMaskSecondaryFn,
    kCGEventFlagMaskShift,
    kCGEventKeyDown,
    kCGEventKeyUp,
    kCGEventTapDisabledByTimeout,
    kCGEventTapOptionDefault,
    kCGHeadInsertEventTap,
    kCGKeyboardEventKeycode,
    kCGSessionEventTap,
    kCGEventSourceStateHIDSystemState,
    NSEvent,
    NSSystemDefined,
)

from plover import log
from plover.key_combo import add_modifiers_aliases, parse_key_combo, KEYNAME_TO_CHAR
from plover.machine.keyboard_capture import Capture
from plover.output.keyboard import GenericKeyboardEmulation

from .keyboardlayout import KeyboardLayout


BACK_SPACE = 51

NX_KEY_OFFSET = 65536

NX_KEYS = {
    "AudioRaiseVolume": 0,
    "AudioLowerVolume": 1,
    "MonBrightnessUp": 2,
    "MonBrightnessDown": 3,
    "AudioMute": 7,
    "Num_Lock": 10,
    "Eject": 14,
    "AudioPause": 16,
    "AudioPlay": 16,
    "AudioNext": 17,
    "AudioPrev": 18,
    "AudioRewind": 20,
    "KbdBrightnessUp": 21,
    "KbdBrightnessDown": 22,
}

KEYNAME_TO_KEYCODE = {
    "fn": 63,
    "alt_l": 58,
    "alt_r": 61,
    "control_l": 59,
    "control_r": 62,
    "shift_l": 56,
    "shift_r": 60,
    "super_l": 55,
    "super_r": 55,
    "caps_lock": 57,
    "return": 36,
    "tab": 48,
    "backspace": BACK_SPACE,
    "delete": 117,
    "escape": 53,
    "clear": 71,
    "up": 126,
    "down": 125,
    "left": 123,
    "right": 124,
    "page_up": 116,
    "page_down": 121,
    "home": 115,
    "end": 119,
    "f1": 122,
    "f2": 120,
    "f3": 99,
    "f4": 118,
    "f5": 96,
    "f6": 97,
    "f7": 98,
    "f8": 100,
    "f9": 101,
    "f10": 109,
    "f11": 103,
    "f12": 111,
    "f13": 105,
    "f14": 107,
    "f15": 113,
    "f16": 106,
    "f17": 64,
    "f18": 79,
    "f19": 80,
    "f20": 90,
    "kp_0": 82,
    "kp_1": 83,
    "kp_2": 84,
    "kp_3": 85,
    "kp_4": 86,
    "kp_5": 87,
    "kp_6": 88,
    "kp_7": 89,
    "kp_8": 91,
    "kp_9": 92,
    "kp_add": 69,
    "kp_decimal": 65,
    "kp_delete": 71,
    "kp_divide": 75,
    "kp_enter": 76,
    "kp_equal": 81,
    "kp_multiply": 67,
    "kp_subtract": 78,
}
for name, code in NX_KEYS.items():
    KEYNAME_TO_KEYCODE[name.lower()] = code + NX_KEY_OFFSET
add_modifiers_aliases(KEYNAME_TO_KEYCODE)

DEADKEY_SYMBOLS = {
    "dead_acute": "´",
    "dead_circumflex": "^",
    "dead_diaeresis": "¨",
    "dead_grave": "`",
    "dead_tilde": "~",
}


def down(seq):
    return [(x, True) for x in seq]


def up(seq):
    return [(x, False) for x in reversed(seq)]


def down_up(seq):
    return down(seq) + up(seq)


# Maps from keycodes to corresponding event masks.
MODIFIER_KEYS_TO_MASKS = {
    58: kCGEventFlagMaskAlternate,
    61: kCGEventFlagMaskAlternate,
    # As of Sierra we *require* secondary fn to get control to work properly.
    59: kCGEventFlagMaskControl,
    62: kCGEventFlagMaskControl,
    56: kCGEventFlagMaskShift,
    60: kCGEventFlagMaskShift,
    55: kCGEventFlagMaskCommand,
    63: kCGEventFlagMaskSecondaryFn,
}

OUTPUT_SOURCE = CGEventSourceCreate(kCGEventSourceStateHIDSystemState)

# For the purposes of this class, we're only watching these keys.
# We could calculate the keys, but our default layout would be misleading:
#
#     KEYCODE_TO_KEY = {keycode: mac_keycode.CharForKeycode(keycode) \
#             for keycode in range(127)}
KEYCODE_TO_KEY = {
    122: "F1",
    120: "F2",
    99: "F3",
    118: "F4",
    96: "F5",
    97: "F6",
    98: "F7",
    100: "F8",
    101: "F9",
    109: "F10",
    103: "F11",
    111: "F12",
    50: "`",
    29: "0",
    18: "1",
    19: "2",
    20: "3",
    21: "4",
    23: "5",
    22: "6",
    26: "7",
    28: "8",
    25: "9",
    27: "-",
    24: "=",
    12: "q",
    13: "w",
    14: "e",
    15: "r",
    17: "t",
    16: "y",
    32: "u",
    34: "i",
    31: "o",
    35: "p",
    33: "[",
    30: "]",
    42: "\\",
    0: "a",
    1: "s",
    2: "d",
    3: "f",
    5: "g",
    4: "h",
    38: "j",
    40: "k",
    37: "l",
    41: ";",
    39: "'",
    6: "z",
    7: "x",
    8: "c",
    9: "v",
    11: "b",
    45: "n",
    46: "m",
    43: ",",
    47: ".",
    44: "/",
    49: "space",
    BACK_SPACE: "BackSpace",
    117: "Delete",
    125: "Down",
    119: "End",
    53: "Escape",
    115: "Home",
    123: "Left",
    121: "Page_Down",
    116: "Page_Up",
    36: "Return",
    124: "Right",
    48: "Tab",
    126: "Up",
}


def keycode_needs_fn_mask(keycode):
    return (
        keycode >= KEYNAME_TO_KEYCODE["escape"]
        and keycode not in MODIFIER_KEYS_TO_MASKS
    )


class KeyboardCaptureLoop:
    def __init__(self, callback):
        self._callback = callback
        self._loop = None
        self._source = None
        self._tap = None
        self._thread = None

    def _run(self, loop_is_set):
        self._loop = CFRunLoopGetCurrent()
        loop_is_set.set()
        del loop_is_set
        CFRunLoopAddSource(self._loop, self._source, kCFRunLoopCommonModes)
        CFRunLoopRun()

    def start(self):
        self._tap = CGEventTapCreate(
            kCGSessionEventTap,
            kCGHeadInsertEventTap,
            kCGEventTapOptionDefault,
            CGEventMaskBit(kCGEventKeyDown) | CGEventMaskBit(kCGEventKeyUp),
            self._callback,
            None,
        )
        if self._tap is None:
            # TODO: See if there is a nice way to show
            # the user what's needed (or do it for them).
            raise Exception("Enable access for assistive devices.")
        self._source = CFMachPortCreateRunLoopSource(None, self._tap, 0)
        loop_is_set = threading.Event()
        self._thread = threading.Thread(
            target=self._run, args=(loop_is_set,), name="KeyboardCaptureLoop"
        )
        self._thread.start()
        loop_is_set.wait()
        self.toggle_tap(True)

    def toggle_tap(self, enabled):
        CGEventTapEnable(self._tap, enabled)

    def cancel(self):
        if self._loop is not None:
            CFRunLoopStop(self._loop)
        if self._thread is not None:
            self._thread.join()
        if self._tap is not None:
            CFMachPortInvalidate(self._tap)
            CFRelease(self._tap)
        if self._source is not None:
            CFRunLoopSourceInvalidate(self._source)


class KeyboardCapture(Capture):
    _KEYBOARD_EVENTS = {kCGEventKeyDown, kCGEventKeyUp}

    # Don't ignore Fn and Numeric flags so we can handle
    # the arrow and extended (home, end, etc...) keys.
    _PASSTHROUGH_MODIFIERS = ~(
        kCGEventFlagMaskNumericPad
        | kCGEventFlagMaskSecondaryFn
        | kCGEventFlagMaskNonCoalesced
    )

    def __init__(self):
        super().__init__()
        self.key_down = lambda key: None
        self.key_up = lambda key: None
        self._suppressed_keys = set()
        self._event_queue = Queue()
        self._event_thread = None
        self._capture_loop = None

    def _callback(self, proxy, event_type, event, reference):
        """
        Returning the event means that it is passed on
        for further processing by others.

        Returning None means that the event is intercepted.

        Delaying too long in returning appears to cause the
        system to ignore the tap forever after
        (https://github.com/openstenoproject/plover/issues/484#issuecomment-214743466).

        This motivates pushing callbacks to the other side
        of a queue of received events, so that we can return
        from this callback as soon as possible.
        """
        if event_type not in self._KEYBOARD_EVENTS:
            # Don't pass on meta events meant for this event tap.
            if event_type == kCGEventTapDisabledByTimeout:
                # Re-enable the tap and hope we act faster next time.
                self._capture_loop.toggle_tap(True)
                log.warning(
                    "Keystrokes may have been missed, the"
                    "keyboard event tap has been re-enabled."
                )
            return None
        if CGEventGetFlags(event) & self._PASSTHROUGH_MODIFIERS:
            # Don't intercept or suppress the event if it has
            # modifiers and the whole keyboard is not suppressed.
            return event
        keycode = CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode)
        key = KEYCODE_TO_KEY.get(keycode)
        if key is None:
            # Not a supported key, don't intercept or suppress.
            return event
        # Notify supported key event.
        self._event_queue.put_nowait((key, event_type))
        # And suppressed it if asked too.
        return None if key in self._suppressed_keys else event

    def start(self):
        self._capture_loop = KeyboardCaptureLoop(self._callback)
        self._capture_loop.start()
        self._event_thread = threading.Thread(name="KeyboardCapture", target=self._run)
        self._event_thread.start()

    def cancel(self):
        if self._event_thread is not None:
            self._event_queue.put(None)
            self._event_thread.join()
        if self._capture_loop is not None:
            self._capture_loop.cancel()

    def suppress(self, suppressed_keys=()):
        self._suppressed_keys = set(suppressed_keys)

    def _run(self):
        while True:
            event = self._event_queue.get()
            if event is None:
                return
            key, event_type = event
            if event_type == kCGEventKeyUp:
                self.key_up(key)
            else:
                self.key_down(key)


class KeyboardEmulation(GenericKeyboardEmulation):
    RAW_PRESS, STRING_PRESS = range(2)

    def __init__(self):
        super().__init__()
        self._layout = KeyboardLayout()

    def send_backspaces(self, count):
        for _ in self.with_delay(range(count)):
            backspace_down = CGEventCreateKeyboardEvent(OUTPUT_SOURCE, BACK_SPACE, True)
            backspace_up = CGEventCreateKeyboardEvent(OUTPUT_SOURCE, BACK_SPACE, False)
            CGEventPost(kCGSessionEventTap, backspace_down)
            CGEventPost(kCGSessionEventTap, backspace_up)

    def send_string(self, string):
        # Key plan will store the type of output
        # (raw keycodes versus setting string)
        # and the list of keycodes or the goal character.
        key_plan = []

        # apply_raw's properties are used to store
        # the current keycode sequence,
        # and add the sequence to the key plan when called as a function.
        def apply_raw():
            if hasattr(apply_raw, "sequence") and len(apply_raw.sequence) != 0:
                apply_raw.sequence.extend(apply_raw.release_modifiers)
                key_plan.append((self.RAW_PRESS, apply_raw.sequence))
            apply_raw.sequence = []
            apply_raw.release_modifiers = []

        apply_raw()

        last_modifier = None
        for c in string:
            for keycode, modifier in self._layout.char_to_key_sequence(c):
                if keycode is not None:
                    if modifier is not last_modifier:
                        # Flush on modifier change.
                        apply_raw()
                        last_modifier = modifier
                        modifier_keycodes = self._modifier_to_keycodes(modifier)
                        apply_raw.sequence.extend(down(modifier_keycodes))
                        apply_raw.release_modifiers.extend(up(modifier_keycodes))
                    apply_raw.sequence.extend(down_up([keycode]))
                else:
                    # Flush on type change.
                    last_modifier = None
                    apply_raw()
                    key_plan.append((self.STRING_PRESS, c))
        # Flush after string is complete.
        apply_raw()

        # We have a key plan for the whole string, grouping modifiers.
        for press_type, sequence in self.with_delay(key_plan):
            if press_type is self.STRING_PRESS:
                self._send_string_press(sequence)
            elif press_type is self.RAW_PRESS:
                self._send_sequence(sequence)

    @staticmethod
    def _send_string_press(c):
        event = CGEventCreateKeyboardEvent(OUTPUT_SOURCE, 0, True)
        KeyboardEmulation._set_event_string(event, c)
        CGEventPost(kCGSessionEventTap, event)
        event = CGEventCreateKeyboardEvent(OUTPUT_SOURCE, 0, False)
        KeyboardEmulation._set_event_string(event, c)
        CGEventPost(kCGSessionEventTap, event)

    def send_key_combination(self, combo):
        def name_to_code(name):
            # Static key codes
            code = KEYNAME_TO_KEYCODE.get(name)
            if code is not None:
                pass
            # Dead keys
            elif name.startswith("dead_"):
                code, mod = self._layout.deadkey_symbol_to_key_sequence(
                    DEADKEY_SYMBOLS.get(name)
                )[0]
            # Normal keys
            else:
                char = KEYNAME_TO_CHAR.get(name, name)
                code, mods = self._layout.char_to_key_sequence(char)[0]
            return code

        # Parse and validate combo.
        key_events = parse_key_combo(combo, name_to_code)
        # Send events...
        self._send_sequence(key_events)

    @staticmethod
    def _modifier_to_keycodes(modifier):
        keycodes = []
        if modifier & 16:
            keycodes.append(KEYNAME_TO_KEYCODE["control_r"])
        if modifier & 8:
            keycodes.append(KEYNAME_TO_KEYCODE["alt_r"])
        if modifier & 2:
            keycodes.append(KEYNAME_TO_KEYCODE["shift_r"])
        if modifier & 1:
            keycodes.append(KEYNAME_TO_KEYCODE["super_r"])
        return keycodes

    @staticmethod
    def _set_event_string(event, s):
        nb_utf16_codepoints = len(s.encode("utf-16-le")) // 2
        CGEventKeyboardSetUnicodeString(event, nb_utf16_codepoints, s)

    MODS_MASK = (
        kCGEventFlagMaskAlternate
        | kCGEventFlagMaskControl
        | kCGEventFlagMaskShift
        | kCGEventFlagMaskCommand
        | kCGEventFlagMaskSecondaryFn
    )

    @staticmethod
    def _get_media_event(key_id, key_down):
        # Credit: https://gist.github.com/fredrikw/4078034
        flags = 0xA00 if key_down else 0xB00
        return NSEvent.otherEventWithType_location_modifierFlags_timestamp_windowNumber_context_subtype_data1_data2_(  # nopep8: We can't make this line shorter!
            NSSystemDefined, (0, 0), flags, 0, 0, 0, 8, (key_id << 16) | flags, -1
        ).CGEvent()

    def _send_sequence(self, sequence):
        # There is a bug in the event system that seems to cause inconsistent
        # modifiers on key events:
        # http://stackoverflow.com/questions/2008126/cgeventpost-possible-bug-when-simulating-keyboard-events
        # My solution is to manage the state myself.
        # I'm not sure how to deal with caps lock.
        # If mods_flags is not zero at the end then bad things might happen.
        mods_flags = 0

        for keycode, key_down in self.with_delay(sequence):
            if keycode >= NX_KEY_OFFSET:
                # Handle media (NX) key.
                event = KeyboardEmulation._get_media_event(
                    keycode - NX_KEY_OFFSET, key_down
                )
            else:
                # Handle regular keycode.
                if not key_down and keycode in MODIFIER_KEYS_TO_MASKS:
                    mods_flags &= ~MODIFIER_KEYS_TO_MASKS[keycode]

                if key_down and keycode_needs_fn_mask(keycode):
                    mods_flags |= kCGEventFlagMaskSecondaryFn

                event = CGEventCreateKeyboardEvent(OUTPUT_SOURCE, keycode, key_down)

                if key_down and keycode not in MODIFIER_KEYS_TO_MASKS:
                    event_flags = CGEventGetFlags(event)
                    # Add wanted flags, remove unwanted flags.
                    goal_flags = (
                        event_flags & ~KeyboardEmulation.MODS_MASK
                    ) | mods_flags
                    if event_flags != goal_flags:
                        CGEventSetFlags(event, goal_flags)

                    # Half millisecond pause after key down.
                    sleep(0.0005)

                if key_down and keycode in MODIFIER_KEYS_TO_MASKS:
                    mods_flags |= MODIFIER_KEYS_TO_MASKS[keycode]

                if not key_down and keycode_needs_fn_mask(keycode):
                    mods_flags &= ~kCGEventFlagMaskSecondaryFn

            CGEventPost(kCGSessionEventTap, event)
