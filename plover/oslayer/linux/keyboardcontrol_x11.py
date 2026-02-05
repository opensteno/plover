# -*- coding: utf-8 -*-
#
# Copyright (c) 2010 Joshua Harlan Lifton.
# See LICENSE.txt for details.
#
# keyboardcontrol.py - capturing and injecting X keyboard events
#
# This code requires the X Window System with the 'XInput2' and 'XTest'
# extensions and python-xlib with support for said extensions.

"""Keyboard capture and control using Xlib.

This module provides an interface for basic keyboard event capture and
emulation. Set the key_up and key_down functions of the
KeyboardCapture class to capture keyboard input. Call the send_string
and send_backspaces functions of the KeyboardEmulation class to
emulate keyboard input.

For an explanation of keycodes, keysyms, and modifiers, see:
http://tronche.com/gui/x/xlib/input/keyboard-encoding.html

"""

import os
import select
import threading

from Xlib import X, XK
from Xlib.display import Display
from Xlib.ext import xinput, xtest
from Xlib.ext.ge import GenericEventCode

from plover import log
from plover.key_combo import add_modifiers_aliases, parse_key_combo
from plover.machine.keyboard_capture import Capture
from plover.output.keyboard import GenericKeyboardEmulation


# Enable support for media keys.
XK.load_keysym_group("xf86")
# Load non-us keyboard related keysyms.
XK.load_keysym_group("xkb")

# Create case insensitive mapping of keyname to keysym.
KEY_TO_KEYSYM = {}
for symbol in sorted(dir(XK)):  # Sorted so XK_a is preferred over XK_A.
    if not symbol.startswith("XK_"):
        continue
    name = symbol[3:].lower()
    keysym = getattr(XK, symbol)
    KEY_TO_KEYSYM[name] = keysym
    # Add aliases for `XF86_` keys.
    if name.startswith("xf86_"):
        alias = name[5:]
        if alias not in KEY_TO_KEYSYM:
            KEY_TO_KEYSYM[alias] = keysym
add_modifiers_aliases(KEY_TO_KEYSYM)

XINPUT_DEVICE_ID = xinput.AllDevices
XINPUT_EVENT_MASK = xinput.KeyPressMask | xinput.KeyReleaseMask

KEYCODE_TO_KEY = {
    # Function row.
    67: "F1",
    68: "F2",
    69: "F3",
    70: "F4",
    71: "F5",
    72: "F6",
    73: "F7",
    74: "F8",
    75: "F9",
    76: "F10",
    95: "F11",
    96: "F12",
    # Number row.
    49: "`",
    10: "1",
    11: "2",
    12: "3",
    13: "4",
    14: "5",
    15: "6",
    16: "7",
    17: "8",
    18: "9",
    19: "0",
    20: "-",
    21: "=",
    51: "\\",
    # Upper row.
    24: "q",
    25: "w",
    26: "e",
    27: "r",
    28: "t",
    29: "y",
    30: "u",
    31: "i",
    32: "o",
    33: "p",
    34: "[",
    35: "]",
    # Home row.
    38: "a",
    39: "s",
    40: "d",
    41: "f",
    42: "g",
    43: "h",
    44: "j",
    45: "k",
    46: "l",
    47: ";",
    48: "'",
    # Bottom row.
    52: "z",
    53: "x",
    54: "c",
    55: "v",
    56: "b",
    57: "n",
    58: "m",
    59: ",",
    60: ".",
    61: "/",
    # Other keys.
    22: "BackSpace",
    119: "Delete",
    116: "Down",
    115: "End",
    9: "Escape",
    110: "Home",
    118: "Insert",
    113: "Left",
    117: "Page_Down",
    112: "Page_Up",
    36: "Return",
    114: "Right",
    23: "Tab",
    111: "Up",
    65: "space",
}

KEY_TO_KEYCODE = dict(zip(KEYCODE_TO_KEY.values(), KEYCODE_TO_KEY.keys()))


class XEventLoop:
    def __init__(self, on_event, name="XEventLoop"):
        self._on_event = on_event
        self._lock = threading.Lock()
        self._display = Display()
        self._thread = threading.Thread(name=name, target=self._run)
        self._pipe = os.pipe()
        self._readfds = (self._pipe[0], self._display.fileno())

    def __enter__(self):
        self._lock.__enter__()
        return self._display

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is None and self._display is not None:
            self._display.sync()
        self._lock.__exit__(exc_type, exc_value, traceback)

    def _process_pending_events(self):
        for __ in range(self._display.pending_events()):
            self._on_event(self._display.next_event())

    def _run(self):
        while True:
            with self._lock:
                self._process_pending_events()
            # No more events: sleep until we get new data on the
            # display connection, or on the pipe used to signal
            # the end of the loop.
            rlist, wlist, xlist = select.select(self._readfds, (), ())
            assert not wlist
            assert not xlist
            if self._pipe[0] in rlist:
                break
            # If we're here, rlist should contains the display fd,
            # and the next iteration will find some pending events.

    def start(self):
        self._thread.start()

    def cancel(self):
        if self._thread.is_alive():
            # Wake up the capture thread...
            os.write(self._pipe[1], b"quit")
            # ...and wait for it to terminate.
            self._thread.join()
        for fd in self._pipe:
            os.close(fd)
        self._display.close()
        self._display = None


class KeyboardCapture(Capture):
    def __init__(self):
        super().__init__()
        self._event_loop = None
        self._window = None
        self._suppressed_keys = set()
        self._devices = []

    def _update_devices(self, display):
        # Find all keyboard devices.
        # This function is never called while the event loop thread is running,
        # so it is unnecessary to lock self._display_lock.
        keyboard_devices = []
        for devinfo in display.xinput_query_device(xinput.AllDevices).devices:
            # Only keep slave devices.
            # Note: we look at pointer devices too, as some keyboards (like the
            # VicTop mechanical gaming keyboard) register 2 devices, including
            # a pointer device with a key class (to fully support NKRO).
            if devinfo.use not in (xinput.SlaveKeyboard, xinput.SlavePointer):
                continue
            # Ignore XTest keyboard device.
            if "Virtual core XTEST keyboard" == devinfo.name:
                continue
            # Ignore disabled devices.
            if not devinfo.enabled:
                continue
            # Check for the presence of a key class.
            for c in devinfo.classes:
                if c.type == xinput.KeyClass:
                    keyboard_devices.append(devinfo.deviceid)
                    break
        if XINPUT_DEVICE_ID == xinput.AllDevices:
            self._devices = keyboard_devices
        else:
            self._devices = [XINPUT_DEVICE_ID]
        log.info("XInput devices: %s", ", ".join(map(str, self._devices)))

    def _on_event(self, event):
        if event.type != GenericEventCode:
            return
        if event.evtype not in (xinput.KeyPress, xinput.KeyRelease):
            return
        assert event.data.sourceid in self._devices
        keycode = event.data.detail
        modifiers = event.data.mods.effective_mods & ~0b10000 & 0xFF
        key = KEYCODE_TO_KEY.get(keycode)
        if key is None:
            # Not a supported key, ignore...
            return
        # ...or pass it on to a callback method.
        if event.evtype == xinput.KeyPress:
            # Ignore event if a modifier is set.
            if modifiers == 0:
                self.key_down(key)
        elif event.evtype == xinput.KeyRelease:
            self.key_up(key)

    def start(self):
        self._event_loop = XEventLoop(self._on_event, name="KeyboardCapture")
        with self._event_loop as display:
            if not display.has_extension("XInputExtension"):
                raise Exception(
                    "X11's XInput extension is required, but could not be found."
                )
            self._update_devices(display)
            self._window = display.screen().root
            self._window.xinput_select_events(
                [(deviceid, XINPUT_EVENT_MASK) for deviceid in self._devices]
            )
            self._event_loop.start()

    def cancel(self):
        if self._event_loop is None:
            return
        with self._event_loop:
            self._suppress_keys(())
        self._event_loop.cancel()

    def suppress(self, suppressed_keys=()):
        with self._event_loop:
            self._suppress_keys(suppressed_keys)

    def _grab_key(self, keycode):
        for deviceid in self._devices:
            self._window.xinput_grab_keycode(
                deviceid,
                X.CurrentTime,
                keycode,
                xinput.GrabModeAsync,
                xinput.GrabModeAsync,
                True,
                XINPUT_EVENT_MASK,
                (0, X.Mod2Mask),
            )

    def _ungrab_key(self, keycode):
        for deviceid in self._devices:
            self._window.xinput_ungrab_keycode(deviceid, keycode, (0, X.Mod2Mask))

    def _suppress_keys(self, suppressed_keys):
        suppressed_keys = set(suppressed_keys)
        if self._suppressed_keys == suppressed_keys:
            return
        for key in self._suppressed_keys - suppressed_keys:
            self._ungrab_key(KEY_TO_KEYCODE[key])
            self._suppressed_keys.remove(key)
        for key in suppressed_keys - self._suppressed_keys:
            self._grab_key(KEY_TO_KEYCODE[key])
            self._suppressed_keys.add(key)
        assert self._suppressed_keys == suppressed_keys


# Keysym to Unicode conversion table.
# Taken from xterm/keysym2ucs.c
KEYSYM_TO_UCS = {
    0x01A1: 0x0104,  #                     Aogonek Ą LATIN CAPITAL LETTER A WITH OGONEK
    0x01A2: 0x02D8,  #                       breve ˘ BREVE
    0x01A3: 0x0141,  #                     Lstroke Ł LATIN CAPITAL LETTER L WITH STROKE
    0x01A5: 0x013D,  #                      Lcaron Ľ LATIN CAPITAL LETTER L WITH CARON
    0x01A6: 0x015A,  #                      Sacute Ś LATIN CAPITAL LETTER S WITH ACUTE
    0x01A9: 0x0160,  #                      Scaron Š LATIN CAPITAL LETTER S WITH CARON
    0x01AA: 0x015E,  #                    Scedilla Ş LATIN CAPITAL LETTER S WITH CEDILLA
    0x01AB: 0x0164,  #                      Tcaron Ť LATIN CAPITAL LETTER T WITH CARON
    0x01AC: 0x0179,  #                      Zacute Ź LATIN CAPITAL LETTER Z WITH ACUTE
    0x01AE: 0x017D,  #                      Zcaron Ž LATIN CAPITAL LETTER Z WITH CARON
    0x01AF: 0x017B,  #                   Zabovedot Ż LATIN CAPITAL LETTER Z WITH DOT ABOVE
    0x01B1: 0x0105,  #                     aogonek ą LATIN SMALL LETTER A WITH OGONEK
    0x01B2: 0x02DB,  #                      ogonek ˛ OGONEK
    0x01B3: 0x0142,  #                     lstroke ł LATIN SMALL LETTER L WITH STROKE
    0x01B5: 0x013E,  #                      lcaron ľ LATIN SMALL LETTER L WITH CARON
    0x01B6: 0x015B,  #                      sacute ś LATIN SMALL LETTER S WITH ACUTE
    0x01B7: 0x02C7,  #                       caron ˇ CARON
    0x01B9: 0x0161,  #                      scaron š LATIN SMALL LETTER S WITH CARON
    0x01BA: 0x015F,  #                    scedilla ş LATIN SMALL LETTER S WITH CEDILLA
    0x01BB: 0x0165,  #                      tcaron ť LATIN SMALL LETTER T WITH CARON
    0x01BC: 0x017A,  #                      zacute ź LATIN SMALL LETTER Z WITH ACUTE
    0x01BD: 0x02DD,  #                 doubleacute ˝ DOUBLE ACUTE ACCENT
    0x01BE: 0x017E,  #                      zcaron ž LATIN SMALL LETTER Z WITH CARON
    0x01BF: 0x017C,  #                   zabovedot ż LATIN SMALL LETTER Z WITH DOT ABOVE
    0x01C0: 0x0154,  #                      Racute Ŕ LATIN CAPITAL LETTER R WITH ACUTE
    0x01C3: 0x0102,  #                      Abreve Ă LATIN CAPITAL LETTER A WITH BREVE
    0x01C5: 0x0139,  #                      Lacute Ĺ LATIN CAPITAL LETTER L WITH ACUTE
    0x01C6: 0x0106,  #                      Cacute Ć LATIN CAPITAL LETTER C WITH ACUTE
    0x01C8: 0x010C,  #                      Ccaron Č LATIN CAPITAL LETTER C WITH CARON
    0x01CA: 0x0118,  #                     Eogonek Ę LATIN CAPITAL LETTER E WITH OGONEK
    0x01CC: 0x011A,  #                      Ecaron Ě LATIN CAPITAL LETTER E WITH CARON
    0x01CF: 0x010E,  #                      Dcaron Ď LATIN CAPITAL LETTER D WITH CARON
    0x01D0: 0x0110,  #                     Dstroke Đ LATIN CAPITAL LETTER D WITH STROKE
    0x01D1: 0x0143,  #                      Nacute Ń LATIN CAPITAL LETTER N WITH ACUTE
    0x01D2: 0x0147,  #                      Ncaron Ň LATIN CAPITAL LETTER N WITH CARON
    0x01D5: 0x0150,  #                Odoubleacute Ő LATIN CAPITAL LETTER O WITH DOUBLE ACUTE
    0x01D8: 0x0158,  #                      Rcaron Ř LATIN CAPITAL LETTER R WITH CARON
    0x01D9: 0x016E,  #                       Uring Ů LATIN CAPITAL LETTER U WITH RING ABOVE
    0x01DB: 0x0170,  #                Udoubleacute Ű LATIN CAPITAL LETTER U WITH DOUBLE ACUTE
    0x01DE: 0x0162,  #                    Tcedilla Ţ LATIN CAPITAL LETTER T WITH CEDILLA
    0x01E0: 0x0155,  #                      racute ŕ LATIN SMALL LETTER R WITH ACUTE
    0x01E3: 0x0103,  #                      abreve ă LATIN SMALL LETTER A WITH BREVE
    0x01E5: 0x013A,  #                      lacute ĺ LATIN SMALL LETTER L WITH ACUTE
    0x01E6: 0x0107,  #                      cacute ć LATIN SMALL LETTER C WITH ACUTE
    0x01E8: 0x010D,  #                      ccaron č LATIN SMALL LETTER C WITH CARON
    0x01EA: 0x0119,  #                     eogonek ę LATIN SMALL LETTER E WITH OGONEK
    0x01EC: 0x011B,  #                      ecaron ě LATIN SMALL LETTER E WITH CARON
    0x01EF: 0x010F,  #                      dcaron ď LATIN SMALL LETTER D WITH CARON
    0x01F0: 0x0111,  #                     dstroke đ LATIN SMALL LETTER D WITH STROKE
    0x01F1: 0x0144,  #                      nacute ń LATIN SMALL LETTER N WITH ACUTE
    0x01F2: 0x0148,  #                      ncaron ň LATIN SMALL LETTER N WITH CARON
    0x01F5: 0x0151,  #                odoubleacute ő LATIN SMALL LETTER O WITH DOUBLE ACUTE
    0x01F8: 0x0159,  #                      rcaron ř LATIN SMALL LETTER R WITH CARON
    0x01F9: 0x016F,  #                       uring ů LATIN SMALL LETTER U WITH RING ABOVE
    0x01FB: 0x0171,  #                udoubleacute ű LATIN SMALL LETTER U WITH DOUBLE ACUTE
    0x01FE: 0x0163,  #                    tcedilla ţ LATIN SMALL LETTER T WITH CEDILLA
    0x01FF: 0x02D9,  #                    abovedot ˙ DOT ABOVE
    0x02A1: 0x0126,  #                     Hstroke Ħ LATIN CAPITAL LETTER H WITH STROKE
    0x02A6: 0x0124,  #                 Hcircumflex Ĥ LATIN CAPITAL LETTER H WITH CIRCUMFLEX
    0x02A9: 0x0130,  #                   Iabovedot İ LATIN CAPITAL LETTER I WITH DOT ABOVE
    0x02AB: 0x011E,  #                      Gbreve Ğ LATIN CAPITAL LETTER G WITH BREVE
    0x02AC: 0x0134,  #                 Jcircumflex Ĵ LATIN CAPITAL LETTER J WITH CIRCUMFLEX
    0x02B1: 0x0127,  #                     hstroke ħ LATIN SMALL LETTER H WITH STROKE
    0x02B6: 0x0125,  #                 hcircumflex ĥ LATIN SMALL LETTER H WITH CIRCUMFLEX
    0x02B9: 0x0131,  #                    idotless ı LATIN SMALL LETTER DOTLESS I
    0x02BB: 0x011F,  #                      gbreve ğ LATIN SMALL LETTER G WITH BREVE
    0x02BC: 0x0135,  #                 jcircumflex ĵ LATIN SMALL LETTER J WITH CIRCUMFLEX
    0x02C5: 0x010A,  #                   Cabovedot Ċ LATIN CAPITAL LETTER C WITH DOT ABOVE
    0x02C6: 0x0108,  #                 Ccircumflex Ĉ LATIN CAPITAL LETTER C WITH CIRCUMFLEX
    0x02D5: 0x0120,  #                   Gabovedot Ġ LATIN CAPITAL LETTER G WITH DOT ABOVE
    0x02D8: 0x011C,  #                 Gcircumflex Ĝ LATIN CAPITAL LETTER G WITH CIRCUMFLEX
    0x02DD: 0x016C,  #                      Ubreve Ŭ LATIN CAPITAL LETTER U WITH BREVE
    0x02DE: 0x015C,  #                 Scircumflex Ŝ LATIN CAPITAL LETTER S WITH CIRCUMFLEX
    0x02E5: 0x010B,  #                   cabovedot ċ LATIN SMALL LETTER C WITH DOT ABOVE
    0x02E6: 0x0109,  #                 ccircumflex ĉ LATIN SMALL LETTER C WITH CIRCUMFLEX
    0x02F5: 0x0121,  #                   gabovedot ġ LATIN SMALL LETTER G WITH DOT ABOVE
    0x02F8: 0x011D,  #                 gcircumflex ĝ LATIN SMALL LETTER G WITH CIRCUMFLEX
    0x02FD: 0x016D,  #                      ubreve ŭ LATIN SMALL LETTER U WITH BREVE
    0x02FE: 0x015D,  #                 scircumflex ŝ LATIN SMALL LETTER S WITH CIRCUMFLEX
    0x03A2: 0x0138,  #                         kra ĸ LATIN SMALL LETTER KRA
    0x03A3: 0x0156,  #                    Rcedilla Ŗ LATIN CAPITAL LETTER R WITH CEDILLA
    0x03A5: 0x0128,  #                      Itilde Ĩ LATIN CAPITAL LETTER I WITH TILDE
    0x03A6: 0x013B,  #                    Lcedilla Ļ LATIN CAPITAL LETTER L WITH CEDILLA
    0x03AA: 0x0112,  #                     Emacron Ē LATIN CAPITAL LETTER E WITH MACRON
    0x03AB: 0x0122,  #                    Gcedilla Ģ LATIN CAPITAL LETTER G WITH CEDILLA
    0x03AC: 0x0166,  #                      Tslash Ŧ LATIN CAPITAL LETTER T WITH STROKE
    0x03B3: 0x0157,  #                    rcedilla ŗ LATIN SMALL LETTER R WITH CEDILLA
    0x03B5: 0x0129,  #                      itilde ĩ LATIN SMALL LETTER I WITH TILDE
    0x03B6: 0x013C,  #                    lcedilla ļ LATIN SMALL LETTER L WITH CEDILLA
    0x03BA: 0x0113,  #                     emacron ē LATIN SMALL LETTER E WITH MACRON
    0x03BB: 0x0123,  #                    gcedilla ģ LATIN SMALL LETTER G WITH CEDILLA
    0x03BC: 0x0167,  #                      tslash ŧ LATIN SMALL LETTER T WITH STROKE
    0x03BD: 0x014A,  #                         ENG Ŋ LATIN CAPITAL LETTER ENG
    0x03BF: 0x014B,  #                         eng ŋ LATIN SMALL LETTER ENG
    0x03C0: 0x0100,  #                     Amacron Ā LATIN CAPITAL LETTER A WITH MACRON
    0x03C7: 0x012E,  #                     Iogonek Į LATIN CAPITAL LETTER I WITH OGONEK
    0x03CC: 0x0116,  #                   Eabovedot Ė LATIN CAPITAL LETTER E WITH DOT ABOVE
    0x03CF: 0x012A,  #                     Imacron Ī LATIN CAPITAL LETTER I WITH MACRON
    0x03D1: 0x0145,  #                    Ncedilla Ņ LATIN CAPITAL LETTER N WITH CEDILLA
    0x03D2: 0x014C,  #                     Omacron Ō LATIN CAPITAL LETTER O WITH MACRON
    0x03D3: 0x0136,  #                    Kcedilla Ķ LATIN CAPITAL LETTER K WITH CEDILLA
    0x03D9: 0x0172,  #                     Uogonek Ų LATIN CAPITAL LETTER U WITH OGONEK
    0x03DD: 0x0168,  #                      Utilde Ũ LATIN CAPITAL LETTER U WITH TILDE
    0x03DE: 0x016A,  #                     Umacron Ū LATIN CAPITAL LETTER U WITH MACRON
    0x03E0: 0x0101,  #                     amacron ā LATIN SMALL LETTER A WITH MACRON
    0x03E7: 0x012F,  #                     iogonek į LATIN SMALL LETTER I WITH OGONEK
    0x03EC: 0x0117,  #                   eabovedot ė LATIN SMALL LETTER E WITH DOT ABOVE
    0x03EF: 0x012B,  #                     imacron ī LATIN SMALL LETTER I WITH MACRON
    0x03F1: 0x0146,  #                    ncedilla ņ LATIN SMALL LETTER N WITH CEDILLA
    0x03F2: 0x014D,  #                     omacron ō LATIN SMALL LETTER O WITH MACRON
    0x03F3: 0x0137,  #                    kcedilla ķ LATIN SMALL LETTER K WITH CEDILLA
    0x03F9: 0x0173,  #                     uogonek ų LATIN SMALL LETTER U WITH OGONEK
    0x03FD: 0x0169,  #                      utilde ũ LATIN SMALL LETTER U WITH TILDE
    0x03FE: 0x016B,  #                     umacron ū LATIN SMALL LETTER U WITH MACRON
    0x047E: 0x203E,  #                    overline ‾ OVERLINE
    0x04A1: 0x3002,  #               kana_fullstop 。 IDEOGRAPHIC FULL STOP
    0x04A2: 0x300C,  #         kana_openingbracket 「 LEFT CORNER BRACKET
    0x04A3: 0x300D,  #         kana_closingbracket 」 RIGHT CORNER BRACKET
    0x04A4: 0x3001,  #                  kana_comma 、 IDEOGRAPHIC COMMA
    0x04A5: 0x30FB,  #            kana_conjunctive ・ KATAKANA MIDDLE DOT
    0x04A6: 0x30F2,  #                     kana_WO ヲ KATAKANA LETTER WO
    0x04A7: 0x30A1,  #                      kana_a ァ KATAKANA LETTER SMALL A
    0x04A8: 0x30A3,  #                      kana_i ィ KATAKANA LETTER SMALL I
    0x04A9: 0x30A5,  #                      kana_u ゥ KATAKANA LETTER SMALL U
    0x04AA: 0x30A7,  #                      kana_e ェ KATAKANA LETTER SMALL E
    0x04AB: 0x30A9,  #                      kana_o ォ KATAKANA LETTER SMALL O
    0x04AC: 0x30E3,  #                     kana_ya ャ KATAKANA LETTER SMALL YA
    0x04AD: 0x30E5,  #                     kana_yu ュ KATAKANA LETTER SMALL YU
    0x04AE: 0x30E7,  #                     kana_yo ョ KATAKANA LETTER SMALL YO
    0x04AF: 0x30C3,  #                    kana_tsu ッ KATAKANA LETTER SMALL TU
    0x04B0: 0x30FC,  #              prolongedsound ー KATAKANA-HIRAGANA PROLONGED SOUND MARK
    0x04B1: 0x30A2,  #                      kana_A ア KATAKANA LETTER A
    0x04B2: 0x30A4,  #                      kana_I イ KATAKANA LETTER I
    0x04B3: 0x30A6,  #                      kana_U ウ KATAKANA LETTER U
    0x04B4: 0x30A8,  #                      kana_E エ KATAKANA LETTER E
    0x04B5: 0x30AA,  #                      kana_O オ KATAKANA LETTER O
    0x04B6: 0x30AB,  #                     kana_KA カ KATAKANA LETTER KA
    0x04B7: 0x30AD,  #                     kana_KI キ KATAKANA LETTER KI
    0x04B8: 0x30AF,  #                     kana_KU ク KATAKANA LETTER KU
    0x04B9: 0x30B1,  #                     kana_KE ケ KATAKANA LETTER KE
    0x04BA: 0x30B3,  #                     kana_KO コ KATAKANA LETTER KO
    0x04BB: 0x30B5,  #                     kana_SA サ KATAKANA LETTER SA
    0x04BC: 0x30B7,  #                    kana_SHI シ KATAKANA LETTER SI
    0x04BD: 0x30B9,  #                     kana_SU ス KATAKANA LETTER SU
    0x04BE: 0x30BB,  #                     kana_SE セ KATAKANA LETTER SE
    0x04BF: 0x30BD,  #                     kana_SO ソ KATAKANA LETTER SO
    0x04C0: 0x30BF,  #                     kana_TA タ KATAKANA LETTER TA
    0x04C1: 0x30C1,  #                    kana_CHI チ KATAKANA LETTER TI
    0x04C2: 0x30C4,  #                    kana_TSU ツ KATAKANA LETTER TU
    0x04C3: 0x30C6,  #                     kana_TE テ KATAKANA LETTER TE
    0x04C4: 0x30C8,  #                     kana_TO ト KATAKANA LETTER TO
    0x04C5: 0x30CA,  #                     kana_NA ナ KATAKANA LETTER NA
    0x04C6: 0x30CB,  #                     kana_NI ニ KATAKANA LETTER NI
    0x04C7: 0x30CC,  #                     kana_NU ヌ KATAKANA LETTER NU
    0x04C8: 0x30CD,  #                     kana_NE ネ KATAKANA LETTER NE
    0x04C9: 0x30CE,  #                     kana_NO ノ KATAKANA LETTER NO
    0x04CA: 0x30CF,  #                     kana_HA ハ KATAKANA LETTER HA
    0x04CB: 0x30D2,  #                     kana_HI ヒ KATAKANA LETTER HI
    0x04CC: 0x30D5,  #                     kana_FU フ KATAKANA LETTER HU
    0x04CD: 0x30D8,  #                     kana_HE ヘ KATAKANA LETTER HE
    0x04CE: 0x30DB,  #                     kana_HO ホ KATAKANA LETTER HO
    0x04CF: 0x30DE,  #                     kana_MA マ KATAKANA LETTER MA
    0x04D0: 0x30DF,  #                     kana_MI ミ KATAKANA LETTER MI
    0x04D1: 0x30E0,  #                     kana_MU ム KATAKANA LETTER MU
    0x04D2: 0x30E1,  #                     kana_ME メ KATAKANA LETTER ME
    0x04D3: 0x30E2,  #                     kana_MO モ KATAKANA LETTER MO
    0x04D4: 0x30E4,  #                     kana_YA ヤ KATAKANA LETTER YA
    0x04D5: 0x30E6,  #                     kana_YU ユ KATAKANA LETTER YU
    0x04D6: 0x30E8,  #                     kana_YO ヨ KATAKANA LETTER YO
    0x04D7: 0x30E9,  #                     kana_RA ラ KATAKANA LETTER RA
    0x04D8: 0x30EA,  #                     kana_RI リ KATAKANA LETTER RI
    0x04D9: 0x30EB,  #                     kana_RU ル KATAKANA LETTER RU
    0x04DA: 0x30EC,  #                     kana_RE レ KATAKANA LETTER RE
    0x04DB: 0x30ED,  #                     kana_RO ロ KATAKANA LETTER RO
    0x04DC: 0x30EF,  #                     kana_WA ワ KATAKANA LETTER WA
    0x04DD: 0x30F3,  #                      kana_N ン KATAKANA LETTER N
    0x04DE: 0x309B,  #                 voicedsound ゛ KATAKANA-HIRAGANA VOICED SOUND MARK
    0x04DF: 0x309C,  #             semivoicedsound ゜ KATAKANA-HIRAGANA SEMI-VOICED SOUND MARK
    0x05AC: 0x060C,  #                Arabic_comma ، ARABIC COMMA
    0x05BB: 0x061B,  #            Arabic_semicolon ؛ ARABIC SEMICOLON
    0x05BF: 0x061F,  #        Arabic_question_mark ؟ ARABIC QUESTION MARK
    0x05C1: 0x0621,  #                Arabic_hamza ء ARABIC LETTER HAMZA
    0x05C2: 0x0622,  #          Arabic_maddaonalef آ ARABIC LETTER ALEF WITH MADDA ABOVE
    0x05C3: 0x0623,  #          Arabic_hamzaonalef أ ARABIC LETTER ALEF WITH HAMZA ABOVE
    0x05C4: 0x0624,  #           Arabic_hamzaonwaw ؤ ARABIC LETTER WAW WITH HAMZA ABOVE
    0x05C5: 0x0625,  #       Arabic_hamzaunderalef إ ARABIC LETTER ALEF WITH HAMZA BELOW
    0x05C6: 0x0626,  #           Arabic_hamzaonyeh ئ ARABIC LETTER YEH WITH HAMZA ABOVE
    0x05C7: 0x0627,  #                 Arabic_alef ا ARABIC LETTER ALEF
    0x05C8: 0x0628,  #                  Arabic_beh ب ARABIC LETTER BEH
    0x05C9: 0x0629,  #           Arabic_tehmarbuta ة ARABIC LETTER TEH MARBUTA
    0x05CA: 0x062A,  #                  Arabic_teh ت ARABIC LETTER TEH
    0x05CB: 0x062B,  #                 Arabic_theh ث ARABIC LETTER THEH
    0x05CC: 0x062C,  #                 Arabic_jeem ج ARABIC LETTER JEEM
    0x05CD: 0x062D,  #                  Arabic_hah ح ARABIC LETTER HAH
    0x05CE: 0x062E,  #                 Arabic_khah خ ARABIC LETTER KHAH
    0x05CF: 0x062F,  #                  Arabic_dal د ARABIC LETTER DAL
    0x05D0: 0x0630,  #                 Arabic_thal ذ ARABIC LETTER THAL
    0x05D1: 0x0631,  #                   Arabic_ra ر ARABIC LETTER REH
    0x05D2: 0x0632,  #                 Arabic_zain ز ARABIC LETTER ZAIN
    0x05D3: 0x0633,  #                 Arabic_seen س ARABIC LETTER SEEN
    0x05D4: 0x0634,  #                Arabic_sheen ش ARABIC LETTER SHEEN
    0x05D5: 0x0635,  #                  Arabic_sad ص ARABIC LETTER SAD
    0x05D6: 0x0636,  #                  Arabic_dad ض ARABIC LETTER DAD
    0x05D7: 0x0637,  #                  Arabic_tah ط ARABIC LETTER TAH
    0x05D8: 0x0638,  #                  Arabic_zah ظ ARABIC LETTER ZAH
    0x05D9: 0x0639,  #                  Arabic_ain ع ARABIC LETTER AIN
    0x05DA: 0x063A,  #                Arabic_ghain غ ARABIC LETTER GHAIN
    0x05E0: 0x0640,  #              Arabic_tatweel ـ ARABIC TATWEEL
    0x05E1: 0x0641,  #                  Arabic_feh ف ARABIC LETTER FEH
    0x05E2: 0x0642,  #                  Arabic_qaf ق ARABIC LETTER QAF
    0x05E3: 0x0643,  #                  Arabic_kaf ك ARABIC LETTER KAF
    0x05E4: 0x0644,  #                  Arabic_lam ل ARABIC LETTER LAM
    0x05E5: 0x0645,  #                 Arabic_meem م ARABIC LETTER MEEM
    0x05E6: 0x0646,  #                 Arabic_noon ن ARABIC LETTER NOON
    0x05E7: 0x0647,  #                   Arabic_ha ه ARABIC LETTER HEH
    0x05E8: 0x0648,  #                  Arabic_waw و ARABIC LETTER WAW
    0x05E9: 0x0649,  #          Arabic_alefmaksura ى ARABIC LETTER ALEF MAKSURA
    0x05EA: 0x064A,  #                  Arabic_yeh ي ARABIC LETTER YEH
    0x05EB: 0x064B,  #             Arabic_fathatan ً ARABIC FATHATAN
    0x05EC: 0x064C,  #             Arabic_dammatan ٌ ARABIC DAMMATAN
    0x05ED: 0x064D,  #             Arabic_kasratan ٍ ARABIC KASRATAN
    0x05EE: 0x064E,  #                Arabic_fatha َ ARABIC FATHA
    0x05EF: 0x064F,  #                Arabic_damma ُ ARABIC DAMMA
    0x05F0: 0x0650,  #                Arabic_kasra ِ ARABIC KASRA
    0x05F1: 0x0651,  #               Arabic_shadda ّ ARABIC SHADDA
    0x05F2: 0x0652,  #                Arabic_sukun ْ ARABIC SUKUN
    0x06A1: 0x0452,  #                 Serbian_dje ђ CYRILLIC SMALL LETTER DJE
    0x06A2: 0x0453,  #               Macedonia_gje ѓ CYRILLIC SMALL LETTER GJE
    0x06A3: 0x0451,  #                 Cyrillic_io ё CYRILLIC SMALL LETTER IO
    0x06A4: 0x0454,  #                Ukrainian_ie є CYRILLIC SMALL LETTER UKRAINIAN IE
    0x06A5: 0x0455,  #               Macedonia_dse ѕ CYRILLIC SMALL LETTER DZE
    0x06A6: 0x0456,  #                 Ukrainian_i і CYRILLIC SMALL LETTER BYELORUSSIAN-UKRAINIAN I
    0x06A7: 0x0457,  #                Ukrainian_yi ї CYRILLIC SMALL LETTER YI
    0x06A8: 0x0458,  #                 Cyrillic_je ј CYRILLIC SMALL LETTER JE
    0x06A9: 0x0459,  #                Cyrillic_lje љ CYRILLIC SMALL LETTER LJE
    0x06AA: 0x045A,  #                Cyrillic_nje њ CYRILLIC SMALL LETTER NJE
    0x06AB: 0x045B,  #                Serbian_tshe ћ CYRILLIC SMALL LETTER TSHE
    0x06AC: 0x045C,  #               Macedonia_kje ќ CYRILLIC SMALL LETTER KJE
    0x06AD: 0x0491,  #   Ukrainian_ghe_with_upturn ґ CYRILLIC SMALL LETTER GHE WITH UPTURN
    0x06AE: 0x045E,  #         Byelorussian_shortu ў CYRILLIC SMALL LETTER SHORT U
    0x06AF: 0x045F,  #               Cyrillic_dzhe џ CYRILLIC SMALL LETTER DZHE
    0x06B0: 0x2116,  #                  numerosign № NUMERO SIGN
    0x06B1: 0x0402,  #                 Serbian_DJE Ђ CYRILLIC CAPITAL LETTER DJE
    0x06B2: 0x0403,  #               Macedonia_GJE Ѓ CYRILLIC CAPITAL LETTER GJE
    0x06B3: 0x0401,  #                 Cyrillic_IO Ё CYRILLIC CAPITAL LETTER IO
    0x06B4: 0x0404,  #                Ukrainian_IE Є CYRILLIC CAPITAL LETTER UKRAINIAN IE
    0x06B5: 0x0405,  #               Macedonia_DSE Ѕ CYRILLIC CAPITAL LETTER DZE
    0x06B6: 0x0406,  #                 Ukrainian_I І CYRILLIC CAPITAL LETTER BYELORUSSIAN-UKRAINIAN I
    0x06B7: 0x0407,  #                Ukrainian_YI Ї CYRILLIC CAPITAL LETTER YI
    0x06B8: 0x0408,  #                 Cyrillic_JE Ј CYRILLIC CAPITAL LETTER JE
    0x06B9: 0x0409,  #                Cyrillic_LJE Љ CYRILLIC CAPITAL LETTER LJE
    0x06BA: 0x040A,  #                Cyrillic_NJE Њ CYRILLIC CAPITAL LETTER NJE
    0x06BB: 0x040B,  #                Serbian_TSHE Ћ CYRILLIC CAPITAL LETTER TSHE
    0x06BC: 0x040C,  #               Macedonia_KJE Ќ CYRILLIC CAPITAL LETTER KJE
    0x06BD: 0x0490,  #   Ukrainian_GHE_WITH_UPTURN Ґ CYRILLIC CAPITAL LETTER GHE WITH UPTURN
    0x06BE: 0x040E,  #         Byelorussian_SHORTU Ў CYRILLIC CAPITAL LETTER SHORT U
    0x06BF: 0x040F,  #               Cyrillic_DZHE Џ CYRILLIC CAPITAL LETTER DZHE
    0x06C0: 0x044E,  #                 Cyrillic_yu ю CYRILLIC SMALL LETTER YU
    0x06C1: 0x0430,  #                  Cyrillic_a а CYRILLIC SMALL LETTER A
    0x06C2: 0x0431,  #                 Cyrillic_be б CYRILLIC SMALL LETTER BE
    0x06C3: 0x0446,  #                Cyrillic_tse ц CYRILLIC SMALL LETTER TSE
    0x06C4: 0x0434,  #                 Cyrillic_de д CYRILLIC SMALL LETTER DE
    0x06C5: 0x0435,  #                 Cyrillic_ie е CYRILLIC SMALL LETTER IE
    0x06C6: 0x0444,  #                 Cyrillic_ef ф CYRILLIC SMALL LETTER EF
    0x06C7: 0x0433,  #                Cyrillic_ghe г CYRILLIC SMALL LETTER GHE
    0x06C8: 0x0445,  #                 Cyrillic_ha х CYRILLIC SMALL LETTER HA
    0x06C9: 0x0438,  #                  Cyrillic_i и CYRILLIC SMALL LETTER I
    0x06CA: 0x0439,  #             Cyrillic_shorti й CYRILLIC SMALL LETTER SHORT I
    0x06CB: 0x043A,  #                 Cyrillic_ka к CYRILLIC SMALL LETTER KA
    0x06CC: 0x043B,  #                 Cyrillic_el л CYRILLIC SMALL LETTER EL
    0x06CD: 0x043C,  #                 Cyrillic_em м CYRILLIC SMALL LETTER EM
    0x06CE: 0x043D,  #                 Cyrillic_en н CYRILLIC SMALL LETTER EN
    0x06CF: 0x043E,  #                  Cyrillic_o о CYRILLIC SMALL LETTER O
    0x06D0: 0x043F,  #                 Cyrillic_pe п CYRILLIC SMALL LETTER PE
    0x06D1: 0x044F,  #                 Cyrillic_ya я CYRILLIC SMALL LETTER YA
    0x06D2: 0x0440,  #                 Cyrillic_er р CYRILLIC SMALL LETTER ER
    0x06D3: 0x0441,  #                 Cyrillic_es с CYRILLIC SMALL LETTER ES
    0x06D4: 0x0442,  #                 Cyrillic_te т CYRILLIC SMALL LETTER TE
    0x06D5: 0x0443,  #                  Cyrillic_u у CYRILLIC SMALL LETTER U
    0x06D6: 0x0436,  #                Cyrillic_zhe ж CYRILLIC SMALL LETTER ZHE
    0x06D7: 0x0432,  #                 Cyrillic_ve в CYRILLIC SMALL LETTER VE
    0x06D8: 0x044C,  #           Cyrillic_softsign ь CYRILLIC SMALL LETTER SOFT SIGN
    0x06D9: 0x044B,  #               Cyrillic_yeru ы CYRILLIC SMALL LETTER YERU
    0x06DA: 0x0437,  #                 Cyrillic_ze з CYRILLIC SMALL LETTER ZE
    0x06DB: 0x0448,  #                Cyrillic_sha ш CYRILLIC SMALL LETTER SHA
    0x06DC: 0x044D,  #                  Cyrillic_e э CYRILLIC SMALL LETTER E
    0x06DD: 0x0449,  #              Cyrillic_shcha щ CYRILLIC SMALL LETTER SHCHA
    0x06DE: 0x0447,  #                Cyrillic_che ч CYRILLIC SMALL LETTER CHE
    0x06DF: 0x044A,  #           Cyrillic_hardsign ъ CYRILLIC SMALL LETTER HARD SIGN
    0x06E0: 0x042E,  #                 Cyrillic_YU Ю CYRILLIC CAPITAL LETTER YU
    0x06E1: 0x0410,  #                  Cyrillic_A А CYRILLIC CAPITAL LETTER A
    0x06E2: 0x0411,  #                 Cyrillic_BE Б CYRILLIC CAPITAL LETTER BE
    0x06E3: 0x0426,  #                Cyrillic_TSE Ц CYRILLIC CAPITAL LETTER TSE
    0x06E4: 0x0414,  #                 Cyrillic_DE Д CYRILLIC CAPITAL LETTER DE
    0x06E5: 0x0415,  #                 Cyrillic_IE Е CYRILLIC CAPITAL LETTER IE
    0x06E6: 0x0424,  #                 Cyrillic_EF Ф CYRILLIC CAPITAL LETTER EF
    0x06E7: 0x0413,  #                Cyrillic_GHE Г CYRILLIC CAPITAL LETTER GHE
    0x06E8: 0x0425,  #                 Cyrillic_HA Х CYRILLIC CAPITAL LETTER HA
    0x06E9: 0x0418,  #                  Cyrillic_I И CYRILLIC CAPITAL LETTER I
    0x06EA: 0x0419,  #             Cyrillic_SHORTI Й CYRILLIC CAPITAL LETTER SHORT I
    0x06EB: 0x041A,  #                 Cyrillic_KA К CYRILLIC CAPITAL LETTER KA
    0x06EC: 0x041B,  #                 Cyrillic_EL Л CYRILLIC CAPITAL LETTER EL
    0x06ED: 0x041C,  #                 Cyrillic_EM М CYRILLIC CAPITAL LETTER EM
    0x06EE: 0x041D,  #                 Cyrillic_EN Н CYRILLIC CAPITAL LETTER EN
    0x06EF: 0x041E,  #                  Cyrillic_O О CYRILLIC CAPITAL LETTER O
    0x06F0: 0x041F,  #                 Cyrillic_PE П CYRILLIC CAPITAL LETTER PE
    0x06F1: 0x042F,  #                 Cyrillic_YA Я CYRILLIC CAPITAL LETTER YA
    0x06F2: 0x0420,  #                 Cyrillic_ER Р CYRILLIC CAPITAL LETTER ER
    0x06F3: 0x0421,  #                 Cyrillic_ES С CYRILLIC CAPITAL LETTER ES
    0x06F4: 0x0422,  #                 Cyrillic_TE Т CYRILLIC CAPITAL LETTER TE
    0x06F5: 0x0423,  #                  Cyrillic_U У CYRILLIC CAPITAL LETTER U
    0x06F6: 0x0416,  #                Cyrillic_ZHE Ж CYRILLIC CAPITAL LETTER ZHE
    0x06F7: 0x0412,  #                 Cyrillic_VE В CYRILLIC CAPITAL LETTER VE
    0x06F8: 0x042C,  #           Cyrillic_SOFTSIGN Ь CYRILLIC CAPITAL LETTER SOFT SIGN
    0x06F9: 0x042B,  #               Cyrillic_YERU Ы CYRILLIC CAPITAL LETTER YERU
    0x06FA: 0x0417,  #                 Cyrillic_ZE З CYRILLIC CAPITAL LETTER ZE
    0x06FB: 0x0428,  #                Cyrillic_SHA Ш CYRILLIC CAPITAL LETTER SHA
    0x06FC: 0x042D,  #                  Cyrillic_E Э CYRILLIC CAPITAL LETTER E
    0x06FD: 0x0429,  #              Cyrillic_SHCHA Щ CYRILLIC CAPITAL LETTER SHCHA
    0x06FE: 0x0427,  #                Cyrillic_CHE Ч CYRILLIC CAPITAL LETTER CHE
    0x06FF: 0x042A,  #           Cyrillic_HARDSIGN Ъ CYRILLIC CAPITAL LETTER HARD SIGN
    0x07A1: 0x0386,  #           Greek_ALPHAaccent Ά GREEK CAPITAL LETTER ALPHA WITH TONOS
    0x07A2: 0x0388,  #         Greek_EPSILONaccent Έ GREEK CAPITAL LETTER EPSILON WITH TONOS
    0x07A3: 0x0389,  #             Greek_ETAaccent Ή GREEK CAPITAL LETTER ETA WITH TONOS
    0x07A4: 0x038A,  #            Greek_IOTAaccent Ί GREEK CAPITAL LETTER IOTA WITH TONOS
    0x07A5: 0x03AA,  #         Greek_IOTAdiaeresis Ϊ GREEK CAPITAL LETTER IOTA WITH DIALYTIKA
    0x07A7: 0x038C,  #         Greek_OMICRONaccent Ό GREEK CAPITAL LETTER OMICRON WITH TONOS
    0x07A8: 0x038E,  #         Greek_UPSILONaccent Ύ GREEK CAPITAL LETTER UPSILON WITH TONOS
    0x07A9: 0x03AB,  #       Greek_UPSILONdieresis Ϋ GREEK CAPITAL LETTER UPSILON WITH DIALYTIKA
    0x07AB: 0x038F,  #           Greek_OMEGAaccent Ώ GREEK CAPITAL LETTER OMEGA WITH TONOS
    0x07AE: 0x0385,  #        Greek_accentdieresis ΅ GREEK DIALYTIKA TONOS
    0x07AF: 0x2015,  #              Greek_horizbar ― HORIZONTAL BAR
    0x07B1: 0x03AC,  #           Greek_alphaaccent ά GREEK SMALL LETTER ALPHA WITH TONOS
    0x07B2: 0x03AD,  #         Greek_epsilonaccent έ GREEK SMALL LETTER EPSILON WITH TONOS
    0x07B3: 0x03AE,  #             Greek_etaaccent ή GREEK SMALL LETTER ETA WITH TONOS
    0x07B4: 0x03AF,  #            Greek_iotaaccent ί GREEK SMALL LETTER IOTA WITH TONOS
    0x07B5: 0x03CA,  #          Greek_iotadieresis ϊ GREEK SMALL LETTER IOTA WITH DIALYTIKA
    0x07B6: 0x0390,  #    Greek_iotaaccentdieresis ΐ GREEK SMALL LETTER IOTA WITH DIALYTIKA AND TONOS
    0x07B7: 0x03CC,  #         Greek_omicronaccent ό GREEK SMALL LETTER OMICRON WITH TONOS
    0x07B8: 0x03CD,  #         Greek_upsilonaccent ύ GREEK SMALL LETTER UPSILON WITH TONOS
    0x07B9: 0x03CB,  #       Greek_upsilondieresis ϋ GREEK SMALL LETTER UPSILON WITH DIALYTIKA
    0x07BA: 0x03B0,  # Greek_upsilonaccentdieresis ΰ GREEK SMALL LETTER UPSILON WITH DIALYTIKA AND TONOS
    0x07BB: 0x03CE,  #           Greek_omegaaccent ώ GREEK SMALL LETTER OMEGA WITH TONOS
    0x07C1: 0x0391,  #                 Greek_ALPHA Α GREEK CAPITAL LETTER ALPHA
    0x07C2: 0x0392,  #                  Greek_BETA Β GREEK CAPITAL LETTER BETA
    0x07C3: 0x0393,  #                 Greek_GAMMA Γ GREEK CAPITAL LETTER GAMMA
    0x07C4: 0x0394,  #                 Greek_DELTA Δ GREEK CAPITAL LETTER DELTA
    0x07C5: 0x0395,  #               Greek_EPSILON Ε GREEK CAPITAL LETTER EPSILON
    0x07C6: 0x0396,  #                  Greek_ZETA Ζ GREEK CAPITAL LETTER ZETA
    0x07C7: 0x0397,  #                   Greek_ETA Η GREEK CAPITAL LETTER ETA
    0x07C8: 0x0398,  #                 Greek_THETA Θ GREEK CAPITAL LETTER THETA
    0x07C9: 0x0399,  #                  Greek_IOTA Ι GREEK CAPITAL LETTER IOTA
    0x07CA: 0x039A,  #                 Greek_KAPPA Κ GREEK CAPITAL LETTER KAPPA
    0x07CB: 0x039B,  #                Greek_LAMBDA Λ GREEK CAPITAL LETTER LAMDA
    0x07CC: 0x039C,  #                    Greek_MU Μ GREEK CAPITAL LETTER MU
    0x07CD: 0x039D,  #                    Greek_NU Ν GREEK CAPITAL LETTER NU
    0x07CE: 0x039E,  #                    Greek_XI Ξ GREEK CAPITAL LETTER XI
    0x07CF: 0x039F,  #               Greek_OMICRON Ο GREEK CAPITAL LETTER OMICRON
    0x07D0: 0x03A0,  #                    Greek_PI Π GREEK CAPITAL LETTER PI
    0x07D1: 0x03A1,  #                   Greek_RHO Ρ GREEK CAPITAL LETTER RHO
    0x07D2: 0x03A3,  #                 Greek_SIGMA Σ GREEK CAPITAL LETTER SIGMA
    0x07D4: 0x03A4,  #                   Greek_TAU Τ GREEK CAPITAL LETTER TAU
    0x07D5: 0x03A5,  #               Greek_UPSILON Υ GREEK CAPITAL LETTER UPSILON
    0x07D6: 0x03A6,  #                   Greek_PHI Φ GREEK CAPITAL LETTER PHI
    0x07D7: 0x03A7,  #                   Greek_CHI Χ GREEK CAPITAL LETTER CHI
    0x07D8: 0x03A8,  #                   Greek_PSI Ψ GREEK CAPITAL LETTER PSI
    0x07D9: 0x03A9,  #                 Greek_OMEGA Ω GREEK CAPITAL LETTER OMEGA
    0x07E1: 0x03B1,  #                 Greek_alpha α GREEK SMALL LETTER ALPHA
    0x07E2: 0x03B2,  #                  Greek_beta β GREEK SMALL LETTER BETA
    0x07E3: 0x03B3,  #                 Greek_gamma γ GREEK SMALL LETTER GAMMA
    0x07E4: 0x03B4,  #                 Greek_delta δ GREEK SMALL LETTER DELTA
    0x07E5: 0x03B5,  #               Greek_epsilon ε GREEK SMALL LETTER EPSILON
    0x07E6: 0x03B6,  #                  Greek_zeta ζ GREEK SMALL LETTER ZETA
    0x07E7: 0x03B7,  #                   Greek_eta η GREEK SMALL LETTER ETA
    0x07E8: 0x03B8,  #                 Greek_theta θ GREEK SMALL LETTER THETA
    0x07E9: 0x03B9,  #                  Greek_iota ι GREEK SMALL LETTER IOTA
    0x07EA: 0x03BA,  #                 Greek_kappa κ GREEK SMALL LETTER KAPPA
    0x07EB: 0x03BB,  #                Greek_lambda λ GREEK SMALL LETTER LAMDA
    0x07EC: 0x03BC,  #                    Greek_mu μ GREEK SMALL LETTER MU
    0x07ED: 0x03BD,  #                    Greek_nu ν GREEK SMALL LETTER NU
    0x07EE: 0x03BE,  #                    Greek_xi ξ GREEK SMALL LETTER XI
    0x07EF: 0x03BF,  #               Greek_omicron ο GREEK SMALL LETTER OMICRON
    0x07F0: 0x03C0,  #                    Greek_pi π GREEK SMALL LETTER PI
    0x07F1: 0x03C1,  #                   Greek_rho ρ GREEK SMALL LETTER RHO
    0x07F2: 0x03C3,  #                 Greek_sigma σ GREEK SMALL LETTER SIGMA
    0x07F3: 0x03C2,  #       Greek_finalsmallsigma ς GREEK SMALL LETTER FINAL SIGMA
    0x07F4: 0x03C4,  #                   Greek_tau τ GREEK SMALL LETTER TAU
    0x07F5: 0x03C5,  #               Greek_upsilon υ GREEK SMALL LETTER UPSILON
    0x07F6: 0x03C6,  #                   Greek_phi φ GREEK SMALL LETTER PHI
    0x07F7: 0x03C7,  #                   Greek_chi χ GREEK SMALL LETTER CHI
    0x07F8: 0x03C8,  #                   Greek_psi ψ GREEK SMALL LETTER PSI
    0x07F9: 0x03C9,  #                 Greek_omega ω GREEK SMALL LETTER OMEGA
    0x08A1: 0x23B7,  #                 leftradical ⎷ RADICAL SYMBOL BOTTOM
    0x08A2: 0x250C,  #              topleftradical ┌ BOX DRAWINGS LIGHT DOWN AND RIGHT
    0x08A3: 0x2500,  #              horizconnector ─ BOX DRAWINGS LIGHT HORIZONTAL
    0x08A4: 0x2320,  #                 topintegral ⌠ TOP HALF INTEGRAL
    0x08A5: 0x2321,  #                 botintegral ⌡ BOTTOM HALF INTEGRAL
    0x08A6: 0x2502,  #               vertconnector │ BOX DRAWINGS LIGHT VERTICAL
    0x08A7: 0x23A1,  #            topleftsqbracket ⎡ LEFT SQUARE BRACKET UPPER CORNER
    0x08A8: 0x23A3,  #            botleftsqbracket ⎣ LEFT SQUARE BRACKET LOWER CORNER
    0x08A9: 0x23A4,  #           toprightsqbracket ⎤ RIGHT SQUARE BRACKET UPPER CORNER
    0x08AA: 0x23A6,  #           botrightsqbracket ⎦ RIGHT SQUARE BRACKET LOWER CORNER
    0x08AB: 0x239B,  #               topleftparens ⎛ LEFT PARENTHESIS UPPER HOOK
    0x08AC: 0x239D,  #               botleftparens ⎝ LEFT PARENTHESIS LOWER HOOK
    0x08AD: 0x239E,  #              toprightparens ⎞ RIGHT PARENTHESIS UPPER HOOK
    0x08AE: 0x23A0,  #              botrightparens ⎠ RIGHT PARENTHESIS LOWER HOOK
    0x08AF: 0x23A8,  #        leftmiddlecurlybrace ⎨ LEFT CURLY BRACKET MIDDLE PIECE
    0x08B0: 0x23AC,  #       rightmiddlecurlybrace ⎬ RIGHT CURLY BRACKET MIDDLE PIECE
    0x08BC: 0x2264,  #               lessthanequal ≤ LESS-THAN OR EQUAL TO
    0x08BD: 0x2260,  #                    notequal ≠ NOT EQUAL TO
    0x08BE: 0x2265,  #            greaterthanequal ≥ GREATER-THAN OR EQUAL TO
    0x08BF: 0x222B,  #                    integral ∫ INTEGRAL
    0x08C0: 0x2234,  #                   therefore ∴ THEREFORE
    0x08C1: 0x221D,  #                   variation ∝ PROPORTIONAL TO
    0x08C2: 0x221E,  #                    infinity ∞ INFINITY
    0x08C5: 0x2207,  #                       nabla ∇ NABLA
    0x08C8: 0x223C,  #                 approximate ∼ TILDE OPERATOR
    0x08C9: 0x2243,  #                similarequal ≃ ASYMPTOTICALLY EQUAL TO
    0x08CD: 0x21D4,  #                    ifonlyif ⇔ LEFT RIGHT DOUBLE ARROW
    0x08CE: 0x21D2,  #                     implies ⇒ RIGHTWARDS DOUBLE ARROW
    0x08CF: 0x2261,  #                   identical ≡ IDENTICAL TO
    0x08D6: 0x221A,  #                     radical √ SQUARE ROOT
    0x08DA: 0x2282,  #                  includedin ⊂ SUBSET OF
    0x08DB: 0x2283,  #                    includes ⊃ SUPERSET OF
    0x08DC: 0x2229,  #                intersection ∩ INTERSECTION
    0x08DD: 0x222A,  #                       union ∪ UNION
    0x08DE: 0x2227,  #                  logicaland ∧ LOGICAL AND
    0x08DF: 0x2228,  #                   logicalor ∨ LOGICAL OR
    0x08EF: 0x2202,  #           partialderivative ∂ PARTIAL DIFFERENTIAL
    0x08F6: 0x0192,  #                    function ƒ LATIN SMALL LETTER F WITH HOOK
    0x08FB: 0x2190,  #                   leftarrow ← LEFTWARDS ARROW
    0x08FC: 0x2191,  #                     uparrow ↑ UPWARDS ARROW
    0x08FD: 0x2192,  #                  rightarrow → RIGHTWARDS ARROW
    0x08FE: 0x2193,  #                   downarrow ↓ DOWNWARDS ARROW
    0x09DF: 0x2422,  #                       blank ␢ BLANK SYMBOL
    0x09E0: 0x25C6,  #                soliddiamond ◆ BLACK DIAMOND
    0x09E1: 0x2592,  #                checkerboard ▒ MEDIUM SHADE
    0x09E2: 0x2409,  #                          ht ␉ SYMBOL FOR HORIZONTAL TABULATION
    0x09E3: 0x240C,  #                          ff ␌ SYMBOL FOR FORM FEED
    0x09E4: 0x240D,  #                          cr ␍ SYMBOL FOR CARRIAGE RETURN
    0x09E5: 0x240A,  #                          lf ␊ SYMBOL FOR LINE FEED
    0x09E8: 0x2424,  #                          nl ␤ SYMBOL FOR NEWLINE
    0x09E9: 0x240B,  #                          vt ␋ SYMBOL FOR VERTICAL TABULATION
    0x09EA: 0x2518,  #              lowrightcorner ┘ BOX DRAWINGS LIGHT UP AND LEFT
    0x09EB: 0x2510,  #               uprightcorner ┐ BOX DRAWINGS LIGHT DOWN AND LEFT
    0x09EC: 0x250C,  #                upleftcorner ┌ BOX DRAWINGS LIGHT DOWN AND RIGHT
    0x09ED: 0x2514,  #               lowleftcorner └ BOX DRAWINGS LIGHT UP AND RIGHT
    0x09EE: 0x253C,  #               crossinglines ┼ BOX DRAWINGS LIGHT VERTICAL AND HORIZONTAL
    0x09EF: 0x23BA,  #              horizlinescan1 ⎺ HORIZONTAL SCAN LINE-1
    0x09F0: 0x23BB,  #              horizlinescan3 ⎻ HORIZONTAL SCAN LINE-3
    0x09F1: 0x2500,  #              horizlinescan5 ─ BOX DRAWINGS LIGHT HORIZONTAL
    0x09F2: 0x23BC,  #              horizlinescan7 ⎼ HORIZONTAL SCAN LINE-7
    0x09F3: 0x23BD,  #              horizlinescan9 ⎽ HORIZONTAL SCAN LINE-9
    0x09F4: 0x251C,  #                       leftt ├ BOX DRAWINGS LIGHT VERTICAL AND RIGHT
    0x09F5: 0x2524,  #                      rightt ┤ BOX DRAWINGS LIGHT VERTICAL AND LEFT
    0x09F6: 0x2534,  #                        bott ┴ BOX DRAWINGS LIGHT UP AND HORIZONTAL
    0x09F7: 0x252C,  #                        topt ┬ BOX DRAWINGS LIGHT DOWN AND HORIZONTAL
    0x09F8: 0x2502,  #                     vertbar │ BOX DRAWINGS LIGHT VERTICAL
    0x0AA1: 0x2003,  #                     emspace   EM SPACE
    0x0AA2: 0x2002,  #                     enspace   EN SPACE
    0x0AA3: 0x2004,  #                    em3space   THREE-PER-EM SPACE
    0x0AA4: 0x2005,  #                    em4space   FOUR-PER-EM SPACE
    0x0AA5: 0x2007,  #                  digitspace   FIGURE SPACE
    0x0AA6: 0x2008,  #                  punctspace   PUNCTUATION SPACE
    0x0AA7: 0x2009,  #                   thinspace   THIN SPACE
    0x0AA8: 0x200A,  #                   hairspace   HAIR SPACE
    0x0AA9: 0x2014,  #                      emdash — EM DASH
    0x0AAA: 0x2013,  #                      endash – EN DASH
    0x0AAC: 0x2423,  #                 signifblank ␣ OPEN BOX
    0x0AAE: 0x2026,  #                    ellipsis … HORIZONTAL ELLIPSIS
    0x0AAF: 0x2025,  #             doubbaselinedot ‥ TWO DOT LEADER
    0x0AB0: 0x2153,  #                    onethird ⅓ VULGAR FRACTION ONE THIRD
    0x0AB1: 0x2154,  #                   twothirds ⅔ VULGAR FRACTION TWO THIRDS
    0x0AB2: 0x2155,  #                    onefifth ⅕ VULGAR FRACTION ONE FIFTH
    0x0AB3: 0x2156,  #                   twofifths ⅖ VULGAR FRACTION TWO FIFTHS
    0x0AB4: 0x2157,  #                 threefifths ⅗ VULGAR FRACTION THREE FIFTHS
    0x0AB5: 0x2158,  #                  fourfifths ⅘ VULGAR FRACTION FOUR FIFTHS
    0x0AB6: 0x2159,  #                    onesixth ⅙ VULGAR FRACTION ONE SIXTH
    0x0AB7: 0x215A,  #                  fivesixths ⅚ VULGAR FRACTION FIVE SIXTHS
    0x0AB8: 0x2105,  #                      careof ℅ CARE OF
    0x0ABB: 0x2012,  #                     figdash ‒ FIGURE DASH
    0x0ABC: 0x2329,  #            leftanglebracket 〈 LEFT-POINTING ANGLE BRACKET
    0x0ABD: 0x002E,  #                decimalpoint . FULL STOP
    0x0ABE: 0x232A,  #           rightanglebracket 〉 RIGHT-POINTING ANGLE BRACKET
    0x0AC3: 0x215B,  #                   oneeighth ⅛ VULGAR FRACTION ONE EIGHTH
    0x0AC4: 0x215C,  #                threeeighths ⅜ VULGAR FRACTION THREE EIGHTHS
    0x0AC5: 0x215D,  #                 fiveeighths ⅝ VULGAR FRACTION FIVE EIGHTHS
    0x0AC6: 0x215E,  #                seveneighths ⅞ VULGAR FRACTION SEVEN EIGHTHS
    0x0AC9: 0x2122,  #                   trademark ™ TRADE MARK SIGN
    0x0ACA: 0x2613,  #               signaturemark ☓ SALTIRE
    0x0ACC: 0x25C1,  #            leftopentriangle ◁ WHITE LEFT-POINTING TRIANGLE
    0x0ACD: 0x25B7,  #           rightopentriangle ▷ WHITE RIGHT-POINTING TRIANGLE
    0x0ACE: 0x25CB,  #                emopencircle ○ WHITE CIRCLE
    0x0ACF: 0x25AF,  #             emopenrectangle ▯ WHITE VERTICAL RECTANGLE
    0x0AD0: 0x2018,  #         leftsinglequotemark ‘ LEFT SINGLE QUOTATION MARK
    0x0AD1: 0x2019,  #        rightsinglequotemark ’ RIGHT SINGLE QUOTATION MARK
    0x0AD2: 0x201C,  #         leftdoublequotemark “ LEFT DOUBLE QUOTATION MARK
    0x0AD3: 0x201D,  #        rightdoublequotemark ” RIGHT DOUBLE QUOTATION MARK
    0x0AD4: 0x211E,  #                prescription ℞ PRESCRIPTION TAKE
    0x0AD6: 0x2032,  #                     minutes ′ PRIME
    0x0AD7: 0x2033,  #                     seconds ″ DOUBLE PRIME
    0x0AD9: 0x271D,  #                  latincross ✝ LATIN CROSS
    0x0ADB: 0x25AC,  #            filledrectbullet ▬ BLACK RECTANGLE
    0x0ADC: 0x25C0,  #         filledlefttribullet ◀ BLACK LEFT-POINTING TRIANGLE
    0x0ADD: 0x25B6,  #        filledrighttribullet ▶ BLACK RIGHT-POINTING TRIANGLE
    0x0ADE: 0x25CF,  #              emfilledcircle ● BLACK CIRCLE
    0x0ADF: 0x25AE,  #                emfilledrect ▮ BLACK VERTICAL RECTANGLE
    0x0AE0: 0x25E6,  #            enopencircbullet ◦ WHITE BULLET
    0x0AE1: 0x25AB,  #          enopensquarebullet ▫ WHITE SMALL SQUARE
    0x0AE2: 0x25AD,  #              openrectbullet ▭ WHITE RECTANGLE
    0x0AE3: 0x25B3,  #             opentribulletup △ WHITE UP-POINTING TRIANGLE
    0x0AE4: 0x25BD,  #           opentribulletdown ▽ WHITE DOWN-POINTING TRIANGLE
    0x0AE5: 0x2606,  #                    openstar ☆ WHITE STAR
    0x0AE6: 0x2022,  #          enfilledcircbullet • BULLET
    0x0AE7: 0x25AA,  #            enfilledsqbullet ▪ BLACK SMALL SQUARE
    0x0AE8: 0x25B2,  #           filledtribulletup ▲ BLACK UP-POINTING TRIANGLE
    0x0AE9: 0x25BC,  #         filledtribulletdown ▼ BLACK DOWN-POINTING TRIANGLE
    0x0AEA: 0x261C,  #                 leftpointer ☜ WHITE LEFT POINTING INDEX
    0x0AEB: 0x261E,  #                rightpointer ☞ WHITE RIGHT POINTING INDEX
    0x0AEC: 0x2663,  #                        club ♣ BLACK CLUB SUIT
    0x0AED: 0x2666,  #                     diamond ♦ BLACK DIAMOND SUIT
    0x0AEE: 0x2665,  #                       heart ♥ BLACK HEART SUIT
    0x0AF0: 0x2720,  #                maltesecross ✠ MALTESE CROSS
    0x0AF1: 0x2020,  #                      dagger † DAGGER
    0x0AF2: 0x2021,  #                doubledagger ‡ DOUBLE DAGGER
    0x0AF3: 0x2713,  #                   checkmark ✓ CHECK MARK
    0x0AF4: 0x2717,  #                 ballotcross ✗ BALLOT X
    0x0AF5: 0x266F,  #                musicalsharp ♯ MUSIC SHARP SIGN
    0x0AF6: 0x266D,  #                 musicalflat ♭ MUSIC FLAT SIGN
    0x0AF7: 0x2642,  #                  malesymbol ♂ MALE SIGN
    0x0AF8: 0x2640,  #                femalesymbol ♀ FEMALE SIGN
    0x0AF9: 0x260E,  #                   telephone ☎ BLACK TELEPHONE
    0x0AFA: 0x2315,  #           telephonerecorder ⌕ TELEPHONE RECORDER
    0x0AFB: 0x2117,  #         phonographcopyright ℗ SOUND RECORDING COPYRIGHT
    0x0AFC: 0x2038,  #                       caret ‸ CARET
    0x0AFD: 0x201A,  #          singlelowquotemark ‚ SINGLE LOW-9 QUOTATION MARK
    0x0AFE: 0x201E,  #          doublelowquotemark „ DOUBLE LOW-9 QUOTATION MARK
    0x0BA3: 0x003C,  #                   leftcaret < LESS-THAN SIGN
    0x0BA6: 0x003E,  #                  rightcaret > GREATER-THAN SIGN
    0x0BA8: 0x2228,  #                   downcaret ∨ LOGICAL OR
    0x0BA9: 0x2227,  #                     upcaret ∧ LOGICAL AND
    0x0BC0: 0x00AF,  #                     overbar ¯ MACRON
    0x0BC2: 0x22A5,  #                    downtack ⊥ UP TACK
    0x0BC3: 0x2229,  #                      upshoe ∩ INTERSECTION
    0x0BC4: 0x230A,  #                   downstile ⌊ LEFT FLOOR
    0x0BC6: 0x005F,  #                    underbar _ LOW LINE
    0x0BCA: 0x2218,  #                         jot ∘ RING OPERATOR
    0x0BCC: 0x2395,  #                        quad ⎕ APL FUNCTIONAL SYMBOL QUAD
    0x0BCE: 0x22A4,  #                      uptack ⊤ DOWN TACK
    0x0BCF: 0x25CB,  #                      circle ○ WHITE CIRCLE
    0x0BD3: 0x2308,  #                     upstile ⌈ LEFT CEILING
    0x0BD6: 0x222A,  #                    downshoe ∪ UNION
    0x0BD8: 0x2283,  #                   rightshoe ⊃ SUPERSET OF
    0x0BDA: 0x2282,  #                    leftshoe ⊂ SUBSET OF
    0x0BDC: 0x22A2,  #                    lefttack ⊢ RIGHT TACK
    0x0BFC: 0x22A3,  #                   righttack ⊣ LEFT TACK
    0x0CDF: 0x2017,  #        hebrew_doublelowline ‗ DOUBLE LOW LINE
    0x0CE0: 0x05D0,  #                hebrew_aleph א HEBREW LETTER ALEF
    0x0CE1: 0x05D1,  #                  hebrew_bet ב HEBREW LETTER BET
    0x0CE2: 0x05D2,  #                hebrew_gimel ג HEBREW LETTER GIMEL
    0x0CE3: 0x05D3,  #                hebrew_dalet ד HEBREW LETTER DALET
    0x0CE4: 0x05D4,  #                   hebrew_he ה HEBREW LETTER HE
    0x0CE5: 0x05D5,  #                  hebrew_waw ו HEBREW LETTER VAV
    0x0CE6: 0x05D6,  #                 hebrew_zain ז HEBREW LETTER ZAYIN
    0x0CE7: 0x05D7,  #                 hebrew_chet ח HEBREW LETTER HET
    0x0CE8: 0x05D8,  #                  hebrew_tet ט HEBREW LETTER TET
    0x0CE9: 0x05D9,  #                  hebrew_yod י HEBREW LETTER YOD
    0x0CEA: 0x05DA,  #            hebrew_finalkaph ך HEBREW LETTER FINAL KAF
    0x0CEB: 0x05DB,  #                 hebrew_kaph כ HEBREW LETTER KAF
    0x0CEC: 0x05DC,  #                hebrew_lamed ל HEBREW LETTER LAMED
    0x0CED: 0x05DD,  #             hebrew_finalmem ם HEBREW LETTER FINAL MEM
    0x0CEE: 0x05DE,  #                  hebrew_mem מ HEBREW LETTER MEM
    0x0CEF: 0x05DF,  #             hebrew_finalnun ן HEBREW LETTER FINAL NUN
    0x0CF0: 0x05E0,  #                  hebrew_nun נ HEBREW LETTER NUN
    0x0CF1: 0x05E1,  #               hebrew_samech ס HEBREW LETTER SAMEKH
    0x0CF2: 0x05E2,  #                 hebrew_ayin ע HEBREW LETTER AYIN
    0x0CF3: 0x05E3,  #              hebrew_finalpe ף HEBREW LETTER FINAL PE
    0x0CF4: 0x05E4,  #                   hebrew_pe פ HEBREW LETTER PE
    0x0CF5: 0x05E5,  #            hebrew_finalzade ץ HEBREW LETTER FINAL TSADI
    0x0CF6: 0x05E6,  #                 hebrew_zade צ HEBREW LETTER TSADI
    0x0CF7: 0x05E7,  #                 hebrew_qoph ק HEBREW LETTER QOF
    0x0CF8: 0x05E8,  #                 hebrew_resh ר HEBREW LETTER RESH
    0x0CF9: 0x05E9,  #                 hebrew_shin ש HEBREW LETTER SHIN
    0x0CFA: 0x05EA,  #                  hebrew_taw ת HEBREW LETTER TAV
    0x0DA1: 0x0E01,  #                  Thai_kokai ก THAI CHARACTER KO KAI
    0x0DA2: 0x0E02,  #                Thai_khokhai ข THAI CHARACTER KHO KHAI
    0x0DA3: 0x0E03,  #               Thai_khokhuat ฃ THAI CHARACTER KHO KHUAT
    0x0DA4: 0x0E04,  #               Thai_khokhwai ค THAI CHARACTER KHO KHWAI
    0x0DA5: 0x0E05,  #                Thai_khokhon ฅ THAI CHARACTER KHO KHON
    0x0DA6: 0x0E06,  #             Thai_khorakhang ฆ THAI CHARACTER KHO RAKHANG
    0x0DA7: 0x0E07,  #                 Thai_ngongu ง THAI CHARACTER NGO NGU
    0x0DA8: 0x0E08,  #                Thai_chochan จ THAI CHARACTER CHO CHAN
    0x0DA9: 0x0E09,  #               Thai_choching ฉ THAI CHARACTER CHO CHING
    0x0DAA: 0x0E0A,  #               Thai_chochang ช THAI CHARACTER CHO CHANG
    0x0DAB: 0x0E0B,  #                   Thai_soso ซ THAI CHARACTER SO SO
    0x0DAC: 0x0E0C,  #                Thai_chochoe ฌ THAI CHARACTER CHO CHOE
    0x0DAD: 0x0E0D,  #                 Thai_yoying ญ THAI CHARACTER YO YING
    0x0DAE: 0x0E0E,  #                Thai_dochada ฎ THAI CHARACTER DO CHADA
    0x0DAF: 0x0E0F,  #                Thai_topatak ฏ THAI CHARACTER TO PATAK
    0x0DB0: 0x0E10,  #                Thai_thothan ฐ THAI CHARACTER THO THAN
    0x0DB1: 0x0E11,  #          Thai_thonangmontho ฑ THAI CHARACTER THO NANGMONTHO
    0x0DB2: 0x0E12,  #             Thai_thophuthao ฒ THAI CHARACTER THO PHUTHAO
    0x0DB3: 0x0E13,  #                  Thai_nonen ณ THAI CHARACTER NO NEN
    0x0DB4: 0x0E14,  #                  Thai_dodek ด THAI CHARACTER DO DEK
    0x0DB5: 0x0E15,  #                  Thai_totao ต THAI CHARACTER TO TAO
    0x0DB6: 0x0E16,  #               Thai_thothung ถ THAI CHARACTER THO THUNG
    0x0DB7: 0x0E17,  #              Thai_thothahan ท THAI CHARACTER THO THAHAN
    0x0DB8: 0x0E18,  #               Thai_thothong ธ THAI CHARACTER THO THONG
    0x0DB9: 0x0E19,  #                   Thai_nonu น THAI CHARACTER NO NU
    0x0DBA: 0x0E1A,  #               Thai_bobaimai บ THAI CHARACTER BO BAIMAI
    0x0DBB: 0x0E1B,  #                  Thai_popla ป THAI CHARACTER PO PLA
    0x0DBC: 0x0E1C,  #               Thai_phophung ผ THAI CHARACTER PHO PHUNG
    0x0DBD: 0x0E1D,  #                   Thai_fofa ฝ THAI CHARACTER FO FA
    0x0DBE: 0x0E1E,  #                Thai_phophan พ THAI CHARACTER PHO PHAN
    0x0DBF: 0x0E1F,  #                  Thai_fofan ฟ THAI CHARACTER FO FAN
    0x0DC0: 0x0E20,  #             Thai_phosamphao ภ THAI CHARACTER PHO SAMPHAO
    0x0DC1: 0x0E21,  #                   Thai_moma ม THAI CHARACTER MO MA
    0x0DC2: 0x0E22,  #                  Thai_yoyak ย THAI CHARACTER YO YAK
    0x0DC3: 0x0E23,  #                  Thai_rorua ร THAI CHARACTER RO RUA
    0x0DC4: 0x0E24,  #                     Thai_ru ฤ THAI CHARACTER RU
    0x0DC5: 0x0E25,  #                 Thai_loling ล THAI CHARACTER LO LING
    0x0DC6: 0x0E26,  #                     Thai_lu ฦ THAI CHARACTER LU
    0x0DC7: 0x0E27,  #                 Thai_wowaen ว THAI CHARACTER WO WAEN
    0x0DC8: 0x0E28,  #                 Thai_sosala ศ THAI CHARACTER SO SALA
    0x0DC9: 0x0E29,  #                 Thai_sorusi ษ THAI CHARACTER SO RUSI
    0x0DCA: 0x0E2A,  #                  Thai_sosua ส THAI CHARACTER SO SUA
    0x0DCB: 0x0E2B,  #                  Thai_hohip ห THAI CHARACTER HO HIP
    0x0DCC: 0x0E2C,  #                Thai_lochula ฬ THAI CHARACTER LO CHULA
    0x0DCD: 0x0E2D,  #                   Thai_oang อ THAI CHARACTER O ANG
    0x0DCE: 0x0E2E,  #               Thai_honokhuk ฮ THAI CHARACTER HO NOKHUK
    0x0DCF: 0x0E2F,  #              Thai_paiyannoi ฯ THAI CHARACTER PAIYANNOI
    0x0DD0: 0x0E30,  #                  Thai_saraa ะ THAI CHARACTER SARA A
    0x0DD1: 0x0E31,  #             Thai_maihanakat ั THAI CHARACTER MAI HAN-AKAT
    0x0DD2: 0x0E32,  #                 Thai_saraaa า THAI CHARACTER SARA AA
    0x0DD3: 0x0E33,  #                 Thai_saraam ำ THAI CHARACTER SARA AM
    0x0DD4: 0x0E34,  #                  Thai_sarai ิ THAI CHARACTER SARA I
    0x0DD5: 0x0E35,  #                 Thai_saraii ี THAI CHARACTER SARA II
    0x0DD6: 0x0E36,  #                 Thai_saraue ึ THAI CHARACTER SARA UE
    0x0DD7: 0x0E37,  #                Thai_sarauee ื THAI CHARACTER SARA UEE
    0x0DD8: 0x0E38,  #                  Thai_sarau ุ THAI CHARACTER SARA U
    0x0DD9: 0x0E39,  #                 Thai_sarauu ู THAI CHARACTER SARA UU
    0x0DDA: 0x0E3A,  #                Thai_phinthu ฺ THAI CHARACTER PHINTHU
    0x0DDE: 0x0E3E,  #      Thai_maihanakat_maitho ฾ ???
    0x0DDF: 0x0E3F,  #                   Thai_baht ฿ THAI CURRENCY SYMBOL BAHT
    0x0DE0: 0x0E40,  #                  Thai_sarae เ THAI CHARACTER SARA E
    0x0DE1: 0x0E41,  #                 Thai_saraae แ THAI CHARACTER SARA AE
    0x0DE2: 0x0E42,  #                  Thai_sarao โ THAI CHARACTER SARA O
    0x0DE3: 0x0E43,  #          Thai_saraaimaimuan ใ THAI CHARACTER SARA AI MAIMUAN
    0x0DE4: 0x0E44,  #         Thai_saraaimaimalai ไ THAI CHARACTER SARA AI MAIMALAI
    0x0DE5: 0x0E45,  #            Thai_lakkhangyao ๅ THAI CHARACTER LAKKHANGYAO
    0x0DE6: 0x0E46,  #               Thai_maiyamok ๆ THAI CHARACTER MAIYAMOK
    0x0DE7: 0x0E47,  #              Thai_maitaikhu ็ THAI CHARACTER MAITAIKHU
    0x0DE8: 0x0E48,  #                  Thai_maiek ่ THAI CHARACTER MAI EK
    0x0DE9: 0x0E49,  #                 Thai_maitho ้ THAI CHARACTER MAI THO
    0x0DEA: 0x0E4A,  #                 Thai_maitri ๊ THAI CHARACTER MAI TRI
    0x0DEB: 0x0E4B,  #            Thai_maichattawa ๋ THAI CHARACTER MAI CHATTAWA
    0x0DEC: 0x0E4C,  #            Thai_thanthakhat ์ THAI CHARACTER THANTHAKHAT
    0x0DED: 0x0E4D,  #               Thai_nikhahit ํ THAI CHARACTER NIKHAHIT
    0x0DF0: 0x0E50,  #                 Thai_leksun ๐ THAI DIGIT ZERO
    0x0DF1: 0x0E51,  #                Thai_leknung ๑ THAI DIGIT ONE
    0x0DF2: 0x0E52,  #                Thai_leksong ๒ THAI DIGIT TWO
    0x0DF3: 0x0E53,  #                 Thai_leksam ๓ THAI DIGIT THREE
    0x0DF4: 0x0E54,  #                  Thai_leksi ๔ THAI DIGIT FOUR
    0x0DF5: 0x0E55,  #                  Thai_lekha ๕ THAI DIGIT FIVE
    0x0DF6: 0x0E56,  #                 Thai_lekhok ๖ THAI DIGIT SIX
    0x0DF7: 0x0E57,  #                Thai_lekchet ๗ THAI DIGIT SEVEN
    0x0DF8: 0x0E58,  #                Thai_lekpaet ๘ THAI DIGIT EIGHT
    0x0DF9: 0x0E59,  #                 Thai_lekkao ๙ THAI DIGIT NINE
    0x0EA1: 0x3131,  #               Hangul_Kiyeog ㄱ HANGUL LETTER KIYEOK
    0x0EA2: 0x3132,  #          Hangul_SsangKiyeog ㄲ HANGUL LETTER SSANGKIYEOK
    0x0EA3: 0x3133,  #           Hangul_KiyeogSios ㄳ HANGUL LETTER KIYEOK-SIOS
    0x0EA4: 0x3134,  #                Hangul_Nieun ㄴ HANGUL LETTER NIEUN
    0x0EA5: 0x3135,  #           Hangul_NieunJieuj ㄵ HANGUL LETTER NIEUN-CIEUC
    0x0EA6: 0x3136,  #           Hangul_NieunHieuh ㄶ HANGUL LETTER NIEUN-HIEUH
    0x0EA7: 0x3137,  #               Hangul_Dikeud ㄷ HANGUL LETTER TIKEUT
    0x0EA8: 0x3138,  #          Hangul_SsangDikeud ㄸ HANGUL LETTER SSANGTIKEUT
    0x0EA9: 0x3139,  #                Hangul_Rieul ㄹ HANGUL LETTER RIEUL
    0x0EAA: 0x313A,  #          Hangul_RieulKiyeog ㄺ HANGUL LETTER RIEUL-KIYEOK
    0x0EAB: 0x313B,  #           Hangul_RieulMieum ㄻ HANGUL LETTER RIEUL-MIEUM
    0x0EAC: 0x313C,  #           Hangul_RieulPieub ㄼ HANGUL LETTER RIEUL-PIEUP
    0x0EAD: 0x313D,  #            Hangul_RieulSios ㄽ HANGUL LETTER RIEUL-SIOS
    0x0EAE: 0x313E,  #           Hangul_RieulTieut ㄾ HANGUL LETTER RIEUL-THIEUTH
    0x0EAF: 0x313F,  #          Hangul_RieulPhieuf ㄿ HANGUL LETTER RIEUL-PHIEUPH
    0x0EB0: 0x3140,  #           Hangul_RieulHieuh ㅀ HANGUL LETTER RIEUL-HIEUH
    0x0EB1: 0x3141,  #                Hangul_Mieum ㅁ HANGUL LETTER MIEUM
    0x0EB2: 0x3142,  #                Hangul_Pieub ㅂ HANGUL LETTER PIEUP
    0x0EB3: 0x3143,  #           Hangul_SsangPieub ㅃ HANGUL LETTER SSANGPIEUP
    0x0EB4: 0x3144,  #            Hangul_PieubSios ㅄ HANGUL LETTER PIEUP-SIOS
    0x0EB5: 0x3145,  #                 Hangul_Sios ㅅ HANGUL LETTER SIOS
    0x0EB6: 0x3146,  #            Hangul_SsangSios ㅆ HANGUL LETTER SSANGSIOS
    0x0EB7: 0x3147,  #                Hangul_Ieung ㅇ HANGUL LETTER IEUNG
    0x0EB8: 0x3148,  #                Hangul_Jieuj ㅈ HANGUL LETTER CIEUC
    0x0EB9: 0x3149,  #           Hangul_SsangJieuj ㅉ HANGUL LETTER SSANGCIEUC
    0x0EBA: 0x314A,  #                Hangul_Cieuc ㅊ HANGUL LETTER CHIEUCH
    0x0EBB: 0x314B,  #               Hangul_Khieuq ㅋ HANGUL LETTER KHIEUKH
    0x0EBC: 0x314C,  #                Hangul_Tieut ㅌ HANGUL LETTER THIEUTH
    0x0EBD: 0x314D,  #               Hangul_Phieuf ㅍ HANGUL LETTER PHIEUPH
    0x0EBE: 0x314E,  #                Hangul_Hieuh ㅎ HANGUL LETTER HIEUH
    0x0EBF: 0x314F,  #                    Hangul_A ㅏ HANGUL LETTER A
    0x0EC0: 0x3150,  #                   Hangul_AE ㅐ HANGUL LETTER AE
    0x0EC1: 0x3151,  #                   Hangul_YA ㅑ HANGUL LETTER YA
    0x0EC2: 0x3152,  #                  Hangul_YAE ㅒ HANGUL LETTER YAE
    0x0EC3: 0x3153,  #                   Hangul_EO ㅓ HANGUL LETTER EO
    0x0EC4: 0x3154,  #                    Hangul_E ㅔ HANGUL LETTER E
    0x0EC5: 0x3155,  #                  Hangul_YEO ㅕ HANGUL LETTER YEO
    0x0EC6: 0x3156,  #                   Hangul_YE ㅖ HANGUL LETTER YE
    0x0EC7: 0x3157,  #                    Hangul_O ㅗ HANGUL LETTER O
    0x0EC8: 0x3158,  #                   Hangul_WA ㅘ HANGUL LETTER WA
    0x0EC9: 0x3159,  #                  Hangul_WAE ㅙ HANGUL LETTER WAE
    0x0ECA: 0x315A,  #                   Hangul_OE ㅚ HANGUL LETTER OE
    0x0ECB: 0x315B,  #                   Hangul_YO ㅛ HANGUL LETTER YO
    0x0ECC: 0x315C,  #                    Hangul_U ㅜ HANGUL LETTER U
    0x0ECD: 0x315D,  #                  Hangul_WEO ㅝ HANGUL LETTER WEO
    0x0ECE: 0x315E,  #                   Hangul_WE ㅞ HANGUL LETTER WE
    0x0ECF: 0x315F,  #                   Hangul_WI ㅟ HANGUL LETTER WI
    0x0ED0: 0x3160,  #                   Hangul_YU ㅠ HANGUL LETTER YU
    0x0ED1: 0x3161,  #                   Hangul_EU ㅡ HANGUL LETTER EU
    0x0ED2: 0x3162,  #                   Hangul_YI ㅢ HANGUL LETTER YI
    0x0ED3: 0x3163,  #                    Hangul_I ㅣ HANGUL LETTER I
    0x0ED4: 0x11A8,  #             Hangul_J_Kiyeog ᆨ HANGUL JONGSEONG KIYEOK
    0x0ED5: 0x11A9,  #        Hangul_J_SsangKiyeog ᆩ HANGUL JONGSEONG SSANGKIYEOK
    0x0ED6: 0x11AA,  #         Hangul_J_KiyeogSios ᆪ HANGUL JONGSEONG KIYEOK-SIOS
    0x0ED7: 0x11AB,  #              Hangul_J_Nieun ᆫ HANGUL JONGSEONG NIEUN
    0x0ED8: 0x11AC,  #         Hangul_J_NieunJieuj ᆬ HANGUL JONGSEONG NIEUN-CIEUC
    0x0ED9: 0x11AD,  #         Hangul_J_NieunHieuh ᆭ HANGUL JONGSEONG NIEUN-HIEUH
    0x0EDA: 0x11AE,  #             Hangul_J_Dikeud ᆮ HANGUL JONGSEONG TIKEUT
    0x0EDB: 0x11AF,  #              Hangul_J_Rieul ᆯ HANGUL JONGSEONG RIEUL
    0x0EDC: 0x11B0,  #        Hangul_J_RieulKiyeog ᆰ HANGUL JONGSEONG RIEUL-KIYEOK
    0x0EDD: 0x11B1,  #         Hangul_J_RieulMieum ᆱ HANGUL JONGSEONG RIEUL-MIEUM
    0x0EDE: 0x11B2,  #         Hangul_J_RieulPieub ᆲ HANGUL JONGSEONG RIEUL-PIEUP
    0x0EDF: 0x11B3,  #          Hangul_J_RieulSios ᆳ HANGUL JONGSEONG RIEUL-SIOS
    0x0EE0: 0x11B4,  #         Hangul_J_RieulTieut ᆴ HANGUL JONGSEONG RIEUL-THIEUTH
    0x0EE1: 0x11B5,  #        Hangul_J_RieulPhieuf ᆵ HANGUL JONGSEONG RIEUL-PHIEUPH
    0x0EE2: 0x11B6,  #         Hangul_J_RieulHieuh ᆶ HANGUL JONGSEONG RIEUL-HIEUH
    0x0EE3: 0x11B7,  #              Hangul_J_Mieum ᆷ HANGUL JONGSEONG MIEUM
    0x0EE4: 0x11B8,  #              Hangul_J_Pieub ᆸ HANGUL JONGSEONG PIEUP
    0x0EE5: 0x11B9,  #          Hangul_J_PieubSios ᆹ HANGUL JONGSEONG PIEUP-SIOS
    0x0EE6: 0x11BA,  #               Hangul_J_Sios ᆺ HANGUL JONGSEONG SIOS
    0x0EE7: 0x11BB,  #          Hangul_J_SsangSios ᆻ HANGUL JONGSEONG SSANGSIOS
    0x0EE8: 0x11BC,  #              Hangul_J_Ieung ᆼ HANGUL JONGSEONG IEUNG
    0x0EE9: 0x11BD,  #              Hangul_J_Jieuj ᆽ HANGUL JONGSEONG CIEUC
    0x0EEA: 0x11BE,  #              Hangul_J_Cieuc ᆾ HANGUL JONGSEONG CHIEUCH
    0x0EEB: 0x11BF,  #             Hangul_J_Khieuq ᆿ HANGUL JONGSEONG KHIEUKH
    0x0EEC: 0x11C0,  #              Hangul_J_Tieut ᇀ HANGUL JONGSEONG THIEUTH
    0x0EED: 0x11C1,  #             Hangul_J_Phieuf ᇁ HANGUL JONGSEONG PHIEUPH
    0x0EEE: 0x11C2,  #              Hangul_J_Hieuh ᇂ HANGUL JONGSEONG HIEUH
    0x0EEF: 0x316D,  #     Hangul_RieulYeorinHieuh ㅭ HANGUL LETTER RIEUL-YEORINHIEUH
    0x0EF0: 0x3171,  #    Hangul_SunkyeongeumMieum ㅱ HANGUL LETTER KAPYEOUNMIEUM
    0x0EF1: 0x3178,  #    Hangul_SunkyeongeumPieub ㅸ HANGUL LETTER KAPYEOUNPIEUP
    0x0EF2: 0x317F,  #              Hangul_PanSios ㅿ HANGUL LETTER PANSIOS
    0x0EF3: 0x3181,  #    Hangul_KkogjiDalrinIeung ㆁ HANGUL LETTER YESIEUNG
    0x0EF4: 0x3184,  #   Hangul_SunkyeongeumPhieuf ㆄ HANGUL LETTER KAPYEOUNPHIEUPH
    0x0EF5: 0x3186,  #          Hangul_YeorinHieuh ㆆ HANGUL LETTER YEORINHIEUH
    0x0EF6: 0x318D,  #                Hangul_AraeA ㆍ HANGUL LETTER ARAEA
    0x0EF7: 0x318E,  #               Hangul_AraeAE ㆎ HANGUL LETTER ARAEAE
    0x0EF8: 0x11EB,  #            Hangul_J_PanSios ᇫ HANGUL JONGSEONG PANSIOS
    0x0EF9: 0x11F0,  #  Hangul_J_KkogjiDalrinIeung ᇰ HANGUL JONGSEONG YESIEUNG
    0x0EFA: 0x11F9,  #        Hangul_J_YeorinHieuh ᇹ HANGUL JONGSEONG YEORINHIEUH
    0x0EFF: 0x20A9,  #                  Korean_Won ₩ WON SIGN
    0x13A4: 0x20AC,  #                        Euro € EURO SIGN
    0x13BC: 0x0152,  #                          OE Œ LATIN CAPITAL LIGATURE OE
    0x13BD: 0x0153,  #                          oe œ LATIN SMALL LIGATURE OE
    0x13BE: 0x0178,  #                  Ydiaeresis Ÿ LATIN CAPITAL LETTER Y WITH DIAERESIS
    0x20A0: 0x20A0,  #                     EcuSign ₠ EURO-CURRENCY SIGN
    0x20A1: 0x20A1,  #                   ColonSign ₡ COLON SIGN
    0x20A2: 0x20A2,  #                CruzeiroSign ₢ CRUZEIRO SIGN
    0x20A3: 0x20A3,  #                  FFrancSign ₣ FRENCH FRANC SIGN
    0x20A4: 0x20A4,  #                    LiraSign ₤ LIRA SIGN
    0x20A5: 0x20A5,  #                    MillSign ₥ MILL SIGN
    0x20A6: 0x20A6,  #                   NairaSign ₦ NAIRA SIGN
    0x20A7: 0x20A7,  #                  PesetaSign ₧ PESETA SIGN
    0x20A8: 0x20A8,  #                   RupeeSign ₨ RUPEE SIGN
    0x20A9: 0x20A9,  #                     WonSign ₩ WON SIGN
    0x20AA: 0x20AA,  #               NewSheqelSign ₪ NEW SHEQEL SIGN
    0x20AB: 0x20AB,  #                    DongSign ₫ DONG SIGN
    0x20AC: 0x20AC,  #                    EuroSign € EURO SIGN
}
UCS_TO_KEYSYM = {ucs: keysym for keysym, ucs in KEYSYM_TO_UCS.items()}


def is_latin1(code):
    return 0x20 <= code <= 0x7E or 0xA0 <= code <= 0xFF


def uchr_to_keysym(char):
    code = ord(char)
    # Latin-1 characters: direct, 1:1 mapping.
    if is_latin1(code):
        return code
    if code == 0x09:
        return XK.XK_Tab
    if code in (0x0A, 0x0D):
        return XK.XK_Return
    return UCS_TO_KEYSYM.get(code, code | 0x01000000)


def keysym_to_string(keysym):
    # Latin-1 characters: direct, 1:1 mapping.
    if is_latin1(keysym):
        code = keysym
    elif (keysym & 0xFF000000) == 0x01000000:
        code = keysym & 0x00FFFFFF
    else:
        code = KEYSYM_TO_UCS.get(keysym)
        if code is None:
            keysym_str = XK.keysym_to_string(keysym)
            if keysym_str is None:
                keysym_str = ""
            for c in keysym_str:
                if not c.isprintable():
                    keysym_str = ""
                    break
            return keysym_str
    return chr(code)


class KeyboardEmulation(GenericKeyboardEmulation):
    class Mapping:
        def __init__(self, keycode, modifiers, keysym, custom_mapping=None):
            self.keycode = keycode
            self.modifiers = modifiers
            self.keysym = keysym
            self.custom_mapping = custom_mapping

        def __str__(self):
            return "%u:%x=%x[%s]%s" % (
                self.keycode,
                self.modifiers,
                self.keysym,
                keysym_to_string(self.keysym),
                "" if self.custom_mapping is None else "*",
            )

    # We can use the first 2 entry of a X11 mapping:
    # keycode and keycode+shift. The 3rd entry is a
    # special keysym to mark the mapping.
    CUSTOM_MAPPING_LENGTH = 3
    # Special keysym to mark custom keyboard mappings.
    PLOVER_MAPPING_KEYSYM = 0x01FFFFFF
    # Free unused keysym.
    UNUSED_KEYSYM = 0xFFFFFF  # XK_VoidSymbol

    def __init__(self):
        super().__init__()
        self._display = Display()
        self._update_keymap()

    def _update_keymap(self):
        """Analyse keymap, build a mapping of keysym to (keycode + modifiers),
        and find unused keycodes that can be used for unmapped keysyms.
        """
        self._keymap = {}
        self._custom_mappings_queue = []
        # Analyse X11 keymap.
        keycode = self._display.display.info.min_keycode
        keycode_count = self._display.display.info.max_keycode - keycode + 1
        for mapping in self._display.get_keyboard_mapping(keycode, keycode_count):
            mapping = tuple(mapping)
            while mapping and X.NoSymbol == mapping[-1]:
                mapping = mapping[:-1]
            if not mapping:
                # Free never used before keycode.
                custom_mapping = [self.UNUSED_KEYSYM] * self.CUSTOM_MAPPING_LENGTH
                custom_mapping[-1] = self.PLOVER_MAPPING_KEYSYM
                mapping = custom_mapping
            elif (
                self.CUSTOM_MAPPING_LENGTH == len(mapping)
                and self.PLOVER_MAPPING_KEYSYM == mapping[-1]
            ):
                # Keycode was previously used by Plover.
                custom_mapping = list(mapping)
            else:
                # Used keycode.
                custom_mapping = None
            for keysym_index, keysym in enumerate(mapping):
                if keysym == self.PLOVER_MAPPING_KEYSYM:
                    continue
                if keysym_index not in (0, 1, 4, 5):
                    continue
                modifiers = 0
                if 1 == (keysym_index % 2):
                    # The keycode needs the Shift modifier.
                    modifiers |= X.ShiftMask
                if 4 <= keysym_index <= 5:
                    # 3rd (AltGr) level.
                    modifiers |= X.Mod5Mask
                mapping = self.Mapping(keycode, modifiers, keysym, custom_mapping)
                if keysym != X.NoSymbol and keysym != self.UNUSED_KEYSYM:
                    # Some keysym are mapped multiple times, prefer lower modifiers combos.
                    previous_mapping = self._keymap.get(keysym)
                    if (
                        previous_mapping is None
                        or mapping.modifiers < previous_mapping.modifiers
                    ):
                        self._keymap[keysym] = mapping
                if custom_mapping is not None:
                    self._custom_mappings_queue.append(mapping)
            keycode += 1
        log.debug("keymap:")
        for mapping in sorted(
            self._keymap.values(), key=lambda m: (m.keycode, m.modifiers)
        ):
            log.debug("%s", mapping)
        log.info("%u custom mappings(s)", len(self._custom_mappings_queue))
        # Determine the backspace mapping.
        backspace_keysym = XK.string_to_keysym("BackSpace")
        self._backspace_mapping = self._get_mapping(backspace_keysym)
        assert self._backspace_mapping is not None
        assert self._backspace_mapping.custom_mapping is None
        # Get modifier mapping.
        self.modifier_mapping = self._display.get_modifier_mapping()

    def send_backspaces(self, count):
        for x in self.with_delay(range(count)):
            self._send_keycode(
                self._backspace_mapping.keycode, self._backspace_mapping.modifiers
            )
            self._display.sync()

    def send_string(self, string):
        modifier_mask = 0
        for i, char in enumerate(string):
            keysym = uchr_to_keysym(char)
            # TODO: can we find mappings for multiple keys at a time?
            mapping = self._get_mapping(keysym, automatically_map=False)
            mapping_changed = False
            if mapping is None:
                mapping = self._get_mapping(keysym, automatically_map=True)
                if mapping is None:
                    continue
                self._display.sync()
                self.half_delay()
                mapping_changed = True

            self._change_modifier_state(modifier_mask, mapping.modifiers)
            modifier_mask = mapping.modifiers
            self._send_keycode(mapping.keycode)
            if i == len(string) - 1:
                self._change_modifier_state(modifier_mask, 0)

            self._display.sync()
            if mapping_changed:
                self.half_delay()
            else:
                self.delay()

    def send_key_combination(self, combo):
        # Parse and validate combo.
        key_events = [
            (keycode, X.KeyPress if pressed else X.KeyRelease)
            for keycode, pressed in parse_key_combo(
                combo, self._get_keycode_from_keystring
            )
        ]
        # Emulate the key combination by sending key events.
        for keycode, event_type in self.with_delay(key_events):
            xtest.fake_input(self._display, event_type, keycode)
            self._display.sync()

    def _change_modifier_state(self, old_modifier_mask: int, new_modifier_mask: int):
        """
        Emulate key presses of modifiers in new mask but not old mask,
        and key releases of modifiers in old mask but not new mask.
        """
        for n in range(8):
            if (new_modifier_mask & (1 << n)) and not (old_modifier_mask & (1 << n)):
                xtest.fake_input(self._display, X.KeyPress, self.modifier_mapping[n][0])
            elif not (new_modifier_mask & (1 << n)) and (old_modifier_mask & (1 << n)):
                xtest.fake_input(
                    self._display, X.KeyRelease, self.modifier_mapping[n][0]
                )

    def _send_keycode(self, keycode, modifiers=0):
        """Emulate a key press and release.

        Arguments:

        keycode -- An integer in the inclusive range [8-255].

        modifiers -- An 8-bit bit mask indicating if the key
        pressed is modified by other keys, such as Shift, Capslock,
        Control, and Alt.

        """
        self._change_modifier_state(0, modifiers)
        xtest.fake_input(self._display, X.KeyPress, keycode)
        xtest.fake_input(self._display, X.KeyRelease, keycode)
        self._change_modifier_state(modifiers, 0)

    def _get_keycode_from_keystring(self, keystring):
        """Find the physical key <keystring> is mapped to.

        Return None of if keystring is not mapped.
        """
        keysym = KEY_TO_KEYSYM.get(keystring)
        if keysym is None:
            return None
        mapping = self._get_mapping(keysym, automatically_map=False)
        if mapping is None:
            return None
        return mapping.keycode

    def _get_mapping(self, keysym, automatically_map=True):
        """Return a keycode and modifier mask pair that result in the keysym.

        There is a one-to-many mapping from keysyms to keycode and
        modifiers pairs; this function returns one of the possibly
        many valid mappings, or None if no mapping exists, and a
        new one cannot be added.

        Arguments:

        keysym -- A key symbol.

        """
        mapping = self._keymap.get(keysym)
        if mapping is None:
            # Automatically map?
            if not automatically_map:
                # No.
                return None
            # Can we map it?
            if 0 == len(self._custom_mappings_queue):
                # Nope...
                return None
            mapping = self._custom_mappings_queue.pop(0)
            previous_keysym = mapping.keysym
            keysym_index = mapping.custom_mapping.index(previous_keysym)
            # Update X11 keymap.
            mapping.custom_mapping[keysym_index] = keysym
            self._display.change_keyboard_mapping(
                mapping.keycode, [mapping.custom_mapping]
            )
            # Update our keymap.
            if previous_keysym in self._keymap:
                del self._keymap[previous_keysym]
            mapping.keysym = keysym
            self._keymap[keysym] = mapping
            log.debug("new mapping: %s", mapping)
            # Move custom mapping back at the end of
            # the queue so we don't use it too soon.
            self._custom_mappings_queue.append(mapping)
        elif mapping.custom_mapping is not None:
            # Same as above; prevent mapping
            # from being reused to soon.
            self._custom_mappings_queue.remove(mapping)
            self._custom_mappings_queue.append(mapping)
        return mapping
