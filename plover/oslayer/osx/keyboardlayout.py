#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Author: @abarnert, @willwade, and @morinted
# Code taken and modified from
# <https://github.com/willwade/PyUserInput/blob/master/pykeyboard/mac_keycode.py>
# <https://stackoverflow.com/questions/1918841/how-to-convert-ascii-character-to-cgkeycode>

from threading import Thread
import ctypes
import ctypes.util
import re
import struct
import unicodedata

from PyObjCTools import AppHelper
import AppKit
import Foundation

from plover import log
from plover.key_combo import CHAR_TO_KEYNAME
from plover.misc import popcount_8


carbon_path = ctypes.util.find_library("Carbon")
carbon = ctypes.cdll.LoadLibrary(carbon_path)

CFIndex = ctypes.c_int64


class CFRange(ctypes.Structure):
    _fields_ = [("loc", CFIndex), ("len", CFIndex)]


carbon.TISCopyCurrentKeyboardInputSource.argtypes = []
carbon.TISCopyCurrentKeyboardInputSource.restype = ctypes.c_void_p
carbon.TISCopyCurrentASCIICapableKeyboardLayoutInputSource.argtypes = []
carbon.TISCopyCurrentASCIICapableKeyboardLayoutInputSource.restype = ctypes.c_void_p

carbon.TISGetInputSourceProperty.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
carbon.TISGetInputSourceProperty.restype = ctypes.c_void_p
carbon.LMGetKbdType.argtypes = []
carbon.LMGetKbdType.restype = ctypes.c_uint32
carbon.CFDataGetLength.argtypes = [ctypes.c_void_p]
carbon.CFDataGetLength.restype = ctypes.c_uint64
carbon.CFDataGetBytes.argtypes = [ctypes.c_void_p, CFRange, ctypes.c_void_p]
carbon.CFDataGetBytes.restype = None
carbon.CFRelease.argtypes = [ctypes.c_void_p]
carbon.CFRelease.restype = None

kTISPropertyUnicodeKeyLayoutData = ctypes.c_void_p.in_dll(
    carbon, "kTISPropertyUnicodeKeyLayoutData"
)
kTISPropertyInputSourceID = ctypes.c_void_p.in_dll(carbon, "kTISPropertyInputSourceID")
kTISPropertyInputSourceIsASCIICapable = ctypes.c_void_p.in_dll(
    carbon, "kTISPropertyInputSourceIsASCIICapable"
)
COMMAND = "⌘"
SHIFT = "⇧"
OPTION = "⌥"
CONTROL = "⌃"
CAPS = "⇪"
UNKNOWN = "?"
UNKNOWN_L = "?_L"

KEY_CODE_VISUALIZATION = """
┌───────────────────Layout of Apple Extended Keyboard II───────────────────────┐
│ 53  122 120 99 118  96 97 98 100  101 109 103 111   105 107 113              │
│                                                                              │
│ 50─── 18 19 20 21 23 22 26 28 25 29 27 24 ─────51   114 115 116  71 81 75 67 │
│ 48──── 12 13 14 15 17 16 32 34 31 35 33 30 ────42   117 119 121  89 91 92 78 │
│ 57───── 0  1  2  3  5  4  38 40 37 41 39 ──────36                86 87 88 69 │
│ 56────── 6  7  8  9  11 45 46  43 47 44 ───────56       126      83 84 85 76 │
│ 59── 58─ 55─ ──────────49───────── ─55 ──58 ───59   123 125 124  82─── 65 76 │
└──────────────────────────────────────────────────────────────────────────────┘
Valid keycodes not visible on layout:
  10, 52, 54, 60-64, 66, 68, 70, 72-74, 77, 79, 80,
  90, 93-95, 102, 104, 106, 108, 110, 112, 127
"""

SPECIAL_KEY_NAMES = {
    "\x1b": "Esc",  # Will map both Esc and Clear (key codes 53 and 71)
    "\xa0": "nbsp",
    "\x08": "Bksp",
    "\x05": "Help",
    "\x01": "Home",
    "\x7f": "Del",
    "\x04": "End",
    "\x0c": "PgDn",
    "\x0b": "PgUp",  # \x0b is also the clear character signal
}

DEFAULT_SEQUENCE = ((None, 0),)


def is_printable(string):
    for character in string:
        category = unicodedata.category(character)
        if category[0] in "C":
            # Exception: the "Apple" character that most Mac layouts have
            return False if string != "" else True
        elif category == "Zs" and character != " ":
            return False
        elif category in "Zl, Zp":
            return False
    return True


def get_printable_string(s):
    if s is None:
        return "None"
    return (
        s
        if is_printable(s)
        else SPECIAL_KEY_NAMES.setdefault(s, s.encode("unicode_escape").decode("utf-8"))
    )


class KeyboardLayout:
    def __init__(self, watch_layout=True):
        self._char_to_key_sequence = None
        self._key_sequence_to_char = None
        self._modifier_masks = None
        self._deadkey_symbol_to_key_sequence = None

        # Spawn a thread that responds to system keyboard layout changes.
        if watch_layout:
            self._watcher = Thread(target=self._layout_watcher, name="LayoutWatcher")
            self._watcher.start()

        self._update_layout()

    def _layout_watcher(self):
        layout = self

        class LayoutWatchingCallback(AppKit.NSObject):
            def layoutChanged_(self, event):
                log.info("Mac keyboard layout changed, updating")
                try:
                    layout._update_layout()
                except Exception:
                    log.warning("error during layout update, ignoring")

        center = Foundation.NSDistributedNotificationCenter.defaultCenter()
        watcher_callback = LayoutWatchingCallback.new()
        center.addObserver_selector_name_object_suspensionBehavior_(
            watcher_callback,
            "layoutChanged:",
            "com.apple.Carbon.TISNotifySelectedKeyboardInputSourceChanged",
            None,
            Foundation.NSNotificationSuspensionBehaviorDeliverImmediately,
        )
        AppHelper.runConsoleEventLoop(installInterrupt=True)

    def _update_layout(self):
        char_to_key_sequence, key_sequence_to_char, modifier_masks = (
            KeyboardLayout._get_layout()
        )
        self._char_to_key_sequence = char_to_key_sequence
        self._key_sequence_to_char = key_sequence_to_char
        self._modifier_masks = modifier_masks
        self._deadkey_symbol_to_key_sequence = self._deadkeys_by_symbols()

    def deadkey_symbol_to_key_sequence(self, symbol):
        return self._deadkey_symbol_to_key_sequence.get(symbol, DEFAULT_SEQUENCE)

    def key_code_to_char(self, key_code, modifier=0):
        """Provide a key code and a modifier and it provides the character"""
        return get_printable_string(self._key_sequence_to_char[key_code, modifier])

    def char_to_key_sequence(self, char):
        """Finds the key code and modifier sequence for the character"""
        key_sequence = self._char_to_key_sequence.get(char, DEFAULT_SEQUENCE)
        if not isinstance(key_sequence[0], tuple):
            key_sequence = (key_sequence,)
        return key_sequence

    def _deadkeys_by_symbols(self):
        # We store deadkeys as "characters"; dkX, where X is the symbol.
        symbols = {
            "`": "`",
            "´": "´",
            "^": ("^", "ˆ"),
            "~": ("~", "˜"),
            "¨": "¨",
        }
        deadkeys_by_symbol = {}
        for symbol, equivalent_symbols in symbols.items():
            for equivalent_symbol in equivalent_symbols:
                sequence = self.char_to_key_sequence("dk%s" % equivalent_symbol)
                if sequence[0][0] is not None:
                    deadkeys_by_symbol[symbol] = sequence
        return deadkeys_by_symbol

    def format_modifier_header(self):
        modifiers = (
            "| {}\t".format(KeyboardLayout._modifier_string(mod)).expandtabs(8)
            for mod in sorted(self._modifier_masks.values())
        )
        header = "Keycode\t{}".format("".join(modifiers))
        return "%s\n%s" % (header, re.sub(r"[^|]", "-", header))

    def format_keycode_keys(self, keycode):
        """Returns all the variations of the keycode with modifiers"""
        keys = (
            "| {}\t".format(
                get_printable_string(self._key_sequence_to_char[keycode, mod])
            ).expandtabs(8)
            for mod in sorted(self._modifier_masks.values())
        )

        return "{}\t{}".format(keycode, "".join(keys)).expandtabs(8)

    @staticmethod
    def _modifier_dictionary(modifier_mask):
        """Provide a dictionary of active modifier keys from mod mask"""
        modifiers = {
            SHIFT: False,
            COMMAND: False,
            CONTROL: False,
            OPTION: False,
            CAPS: False,
            UNKNOWN: False,
            UNKNOWN_L: False,
        }
        if modifier_mask & 16:
            modifiers[CONTROL] = True
        if modifier_mask & 8:
            modifiers[OPTION] = True
        if modifier_mask & 4:
            modifiers[CAPS] = True
        if modifier_mask & 2:
            modifiers[SHIFT] = True
        if modifier_mask & 1:
            modifiers[COMMAND] = True
        return modifiers

    @staticmethod
    def _modifier_string(modifier_mask):
        """Turn modifier mask into string representing modifiers"""
        s = ""
        modifiers = KeyboardLayout._modifier_dictionary(modifier_mask)
        for key in modifiers:
            s += key if modifiers[key] else ""
        return s

    @staticmethod
    def _get_layout():
        keyboard_input_source = carbon.TISCopyCurrentKeyboardInputSource()

        layout_source = carbon.TISGetInputSourceProperty(
            keyboard_input_source, kTISPropertyUnicodeKeyLayoutData
        )
        # Some keyboard layouts don't return UnicodeKeyLayoutData so we turn to a different source.
        if layout_source is None:
            carbon.CFRelease(keyboard_input_source)
            keyboard_input_source = (
                carbon.TISCopyCurrentASCIICapableKeyboardLayoutInputSource()
            )
            layout_source = carbon.TISGetInputSourceProperty(
                keyboard_input_source, kTISPropertyUnicodeKeyLayoutData
            )
        layout_size = carbon.CFDataGetLength(layout_source)
        layout_buffer = ctypes.create_string_buffer(b"\000" * layout_size)
        carbon.CFDataGetBytes(
            layout_source, CFRange(0, layout_size), ctypes.byref(layout_buffer)
        )
        keyboard_type = carbon.LMGetKbdType()
        parsed_layout = KeyboardLayout._parse_layout(layout_buffer, keyboard_type)
        carbon.CFRelease(keyboard_input_source)
        return parsed_layout

    @staticmethod
    def _parse_layout(buf, ktype):
        hf, dv, featureinfo, ktcount = struct.unpack_from("HHII", buf)
        offset = struct.calcsize("HHII")
        ktsize = struct.calcsize("IIIIIII")
        kts = [
            struct.unpack_from("IIIIIII", buf, offset + ktsize * i)
            for i in range(ktcount)
        ]
        for i, kt in enumerate(kts):
            if kt[0] <= ktype <= kt[1]:
                kentry = i
                break
        else:
            kentry = 0
        ktf, ktl, modoff, charoff, sroff, stoff, seqoff = kts[kentry]

        # Modifiers
        mf, deftable, mcount = struct.unpack_from("HHI", buf, modoff)
        modtableoff = modoff + struct.calcsize("HHI")
        modtables = struct.unpack_from("B" * mcount, buf, modtableoff)
        modifier_masks = {}
        for i, table in enumerate(modtables):
            modifier_masks.setdefault(table, i)

        # Sequences
        sequences = []
        if seqoff:
            sf, scount = struct.unpack_from("HH", buf, seqoff)
            seqtableoff = seqoff + struct.calcsize("HH")
            lastoff = -1
            for soff in struct.unpack_from("H" * scount, buf, seqtableoff):
                if lastoff >= 0:
                    sequences.append(
                        buf[seqoff + lastoff : seqoff + soff].decode("utf-16")
                    )
                lastoff = soff

        def lookupseq(key):
            if key >= 0xFFFE:
                return None
            if key & 0xC000:
                seq = key & ~0xC000
                if seq < len(sequences):
                    return sequences[seq]
            return chr(key)

        # Dead keys
        deadkeys = []
        if sroff:
            srf, srcount = struct.unpack_from("HH", buf, sroff)
            srtableoff = sroff + struct.calcsize("HH")
            for recoff in struct.unpack_from("I" * srcount, buf, srtableoff):
                cdata, nextstate, ecount, eformat = struct.unpack_from(
                    "HHHH", buf, recoff
                )
                recdataoff = recoff + struct.calcsize("HHHH")
                edata = buf[recdataoff : recdataoff + 4 * ecount]
                deadkeys.append((cdata, nextstate, ecount, eformat, edata))

        if stoff:
            stf, stcount = struct.unpack_from("HH", buf, stoff)
            sttableoff = stoff + struct.calcsize("HH")
            dkterms = struct.unpack_from("H" * stcount, buf, sttableoff)
        else:
            dkterms = []

        # Get char tables
        char_to_key_sequence = {}
        key_sequence_to_char = {}

        deadkey_state_to_key_sequence = {}
        key_sequence_to_deadkey_state = {}

        def favored_modifiers(modifier_a, modifier_b):
            """0 if they are equal, 1 if a is better, -1 if b is better"""
            a_favored_over_b = 0
            modifiers_a = KeyboardLayout._modifier_dictionary(modifier_a)
            modifiers_b = KeyboardLayout._modifier_dictionary(modifier_b)
            count_a = popcount_8(modifier_a)
            count_b = popcount_8(modifier_b)

            # Favor no CAPS modifier
            if modifiers_a[CAPS] and not modifiers_b[CAPS]:
                a_favored_over_b = -1
            elif modifiers_b[CAPS] and not modifiers_a[CAPS]:
                a_favored_over_b = 1
            # Favor no command modifier
            elif modifiers_a[COMMAND] and not modifiers_b[COMMAND]:
                a_favored_over_b = -1
            elif modifiers_b[COMMAND] and not modifiers_a[COMMAND]:
                a_favored_over_b = 1
            # Favor no control modifier
            elif modifiers_a[CONTROL] and not modifiers_b[CONTROL]:
                a_favored_over_b = -1
            elif modifiers_b[CONTROL] and not modifiers_a[CONTROL]:
                a_favored_over_b = 1
            # Finally, favor fewer modifiers
            elif count_a > count_b:
                a_favored_over_b = -1
            elif count_b > count_a:
                a_favored_over_b = 1
            return a_favored_over_b

        def save_shortest_key_sequence(character, new_sequence):
            current_sequence = char_to_key_sequence.setdefault(character, new_sequence)
            if current_sequence != new_sequence:
                # Convert responses to tuples...
                if not isinstance(current_sequence[0], tuple):
                    current_sequence = (current_sequence,)
                if not isinstance(new_sequence[0], tuple):
                    new_sequence = (new_sequence,)

                first_current_better = favored_modifiers(
                    current_sequence[-1][1], new_sequence[-1][1]
                )
                last_current_better = favored_modifiers(
                    current_sequence[0][1], new_sequence[0][1]
                )

                # Favor key sequence with best modifiers (avoids a short sequence with awful modifiers)
                # e.g. ABC Extended wants ¯ from (⌘⌥a,) instead of the saner (⌥a, space)
                if first_current_better == last_current_better != 0:
                    if first_current_better < 0:
                        char_to_key_sequence[character] = new_sequence
                # Favor shortest sequence (fewer separate key presses)
                elif len(current_sequence) < len(new_sequence):
                    pass
                elif len(new_sequence) < len(current_sequence):
                    char_to_key_sequence[character] = new_sequence[0]
                # Favor fewer modifiers on last item
                elif last_current_better < 0:
                    char_to_key_sequence[character] = new_sequence
                # Favor lower modifiers on first item if last item is the same
                elif last_current_better == 0 and first_current_better < 0:
                    char_to_key_sequence[character] = new_sequence

        def lookup_and_add(key, j, mod):
            ch = lookupseq(key)
            save_shortest_key_sequence(ch, (j, mod))
            key_sequence_to_char[j, mod] = ch

        cf, csize, ccount = struct.unpack_from("HHI", buf, charoff)
        chartableoff = charoff + struct.calcsize("HHI")

        for i, table_offset in enumerate(
            struct.unpack_from("I" * ccount, buf, chartableoff)
        ):
            mod = modifier_masks[i]
            for j, key in enumerate(struct.unpack_from("H" * csize, buf, table_offset)):
                if key == 65535:
                    key_sequence_to_char[j, mod] = "mod"
                elif key >= 0xFFFE:
                    key_sequence_to_char[j, mod] = "<{}>".format(key)
                elif key & 0x0C000 == 0x4000:
                    dead = key & ~0xC000
                    if dead < len(deadkeys):
                        cdata, nextstate, ecount, eformat, edata = deadkeys[dead]
                        if eformat == 0 and nextstate:
                            # Initial: symbols, e.g. `, ~, ^
                            new_deadkey = (j, mod)
                            current_deadkey = deadkey_state_to_key_sequence.setdefault(
                                nextstate, new_deadkey
                            )
                            if new_deadkey != current_deadkey:
                                if (
                                    favored_modifiers(
                                        current_deadkey[1], new_deadkey[1]
                                    )
                                    < 0
                                ):
                                    deadkey_state_to_key_sequence[nextstate] = (
                                        new_deadkey
                                    )
                            if nextstate - 1 < len(dkterms):
                                base_key = lookupseq(dkterms[nextstate - 1])
                                dead_key_name = "dk{}".format(base_key)
                            else:
                                dead_key_name = "dk#{}".format(nextstate)
                            key_sequence_to_char[j, mod] = dead_key_name
                            save_shortest_key_sequence(dead_key_name, (j, mod))
                        elif eformat == 1 or (eformat == 0 and not nextstate):
                            # Terminal: letters, e.g. a, e, o, A, E, O
                            key_sequence_to_deadkey_state[j, mod] = deadkeys[dead]

                            lookup_and_add(cdata, j, mod)
                        elif eformat == 2:  # range
                            # TODO!
                            pass
                else:
                    lookup_and_add(key, j, mod)

        for key, dead in key_sequence_to_deadkey_state.items():
            j, mod = key
            cdata, nextstate, ecount, eformat, edata = dead
            entries = [struct.unpack_from("HH", edata, i * 4) for i in range(ecount)]
            for state, key in entries:
                # Ignore if unknown state...
                if state in deadkey_state_to_key_sequence:
                    dj, dmod = deadkey_state_to_key_sequence[state]
                    ch = lookupseq(key)
                    save_shortest_key_sequence(ch, ((dj, dmod), (j, mod)))
                    key_sequence_to_char[(dj, dmod), (j, mod)] = ch

        char_to_key_sequence["\n"] = (36, 0)
        char_to_key_sequence["\r"] = (36, 0)
        char_to_key_sequence["\t"] = (48, 0)

        return char_to_key_sequence, key_sequence_to_char, modifier_masks


if __name__ == "__main__":
    layout = KeyboardLayout(False)
    print(KEY_CODE_VISUALIZATION)
    print()
    print(layout.format_modifier_header())
    for keycode in range(127):
        print(layout.format_keycode_keys(keycode))
    print()
    unmapped_characters = []
    for char, keyname in sorted(CHAR_TO_KEYNAME.items()):
        sequence = []
        for code, mod in layout.char_to_key_sequence(char):
            if code is not None:
                sequence.append(
                    (
                        code,
                        "{}{}".format(
                            layout._modifier_string(mod),
                            layout.key_code_to_char(code, 0),
                        ),
                    )
                )
            else:
                unmapped_characters.append(char)
        if sequence:
            print(
                "Name:\t\t{}\nCharacter:\t{}\nSequence:\t‘{}’\nBase codes:\t‘{}’\n".format(
                    keyname,
                    char,
                    "’, ‘".join(combo[1] for combo in sequence),
                    "’, ‘".join(str(combo[0]) for combo in sequence),
                )
            )
    print(
        "No mapping on this layout for characters: ‘{}’".format(
            "’, ‘".join(unmapped_characters)
        )
    )
