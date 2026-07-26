import codecs
import ctypes
import sys
from collections import defaultdict, namedtuple
from ctypes import windll, wintypes

from plover.key_combo import CHAR_TO_KEYNAME, add_modifiers_aliases
from plover.misc import popcount_8

from .wmctrl import GetForegroundWindow

GetKeyboardLayout = windll.user32.GetKeyboardLayout
GetKeyboardLayout.argtypes = [
    wintypes.DWORD,  # idThread
]
GetKeyboardLayout.restype = wintypes.HKL

GetWindowThreadProcessId = windll.user32.GetWindowThreadProcessId
GetWindowThreadProcessId.argtypes = [
    wintypes.HWND,  # hWnd
    wintypes.LPDWORD,  # lpdwProcessId
]
GetWindowThreadProcessId.restype = wintypes.DWORD

MapVirtualKeyEx = windll.user32.MapVirtualKeyExW
MapVirtualKeyEx.argtypes = [
    wintypes.UINT,  # uCode,
    wintypes.UINT,  # uMapType,
    wintypes.HKL,  # dwhkl
]
MapVirtualKeyEx.restype = wintypes.UINT

ToUnicodeEx = windll.user32.ToUnicodeEx
ToUnicodeEx.argtypes = [
    wintypes.UINT,  # wVirtKey,
    wintypes.UINT,  # wScanCode,
    wintypes.LPBYTE,  # lpKeyState,
    wintypes.LPWSTR,  # pwszBuff,
    ctypes.c_int,  # cchBuff,
    wintypes.UINT,  # wFlags,
    wintypes.HKL,  # dwhkl
]
ToUnicodeEx.restype = ctypes.c_int


def enum(name, items):
    """Helper to simulate an Enum."""
    keys, values = zip(*items)
    t = namedtuple(name, keys)
    return t._make(values)


# Shift state enum. {{{

SHIFT_STATE = enum(
    "SHIFT_STATE",
    (
        (mod, n)
        for n, mod in enumerate(
            [
                "BASE",
                "SHIFT",
                "CTRL",
                "SHIFT_CTRL",
                "MENU",
                "SHIFT_MENU",
                "MENU_CTRL",
                "SHIFT_MENU_CTRL",
            ]
        )
    ),
)


def shift_state_str(ss):
    s = ""
    for mod_state, mod_str in (
        (SHIFT_STATE.SHIFT, "SHIFT"),
        (SHIFT_STATE.CTRL, "CTRL"),
        (SHIFT_STATE.MENU, "MENU"),
    ):
        if (ss & mod_state) != 0:
            s += mod_str + "+"
    return s


# }}}

# Virtual keys enum. {{{
# fmt: off
vk_dict = {
    "LBUTTON"            : 0x01,
    "RBUTTON"            : 0x02,
    "CANCEL"             : 0x03,
    "MBUTTON"            : 0x04,
    "XBUTTON1"           : 0x05,
    "XBUTTON2"           : 0x06,
    "BACK"               : 0x08,
    "TAB"                : 0x09,
    "CLEAR"              : 0x0C,
    "RETURN"             : 0x0D,
    "SHIFT"              : 0x10,
    "CONTROL"            : 0x11,
    "MENU"               : 0x12,
    "PAUSE"              : 0x13,
    "CAPITAL"            : 0x14,
    "KANA"               : 0x15,
    "JUNJA"              : 0x17,
    "FINAL"              : 0x18,
    "HANJA"              : 0x19,
    "ESCAPE"             : 0x1B,
    "CONVERT"            : 0x1C,
    "NONCONVERT"         : 0x1D,
    "ACCEPT"             : 0x1E,
    "MODECHANGE"         : 0x1F,
    "SPACE"              : 0x20,
    "PRIOR"              : 0x21,
    "NEXT"               : 0x22,
    "END"                : 0x23,
    "HOME"               : 0x24,
    "LEFT"               : 0x25,
    "UP"                 : 0x26,
    "RIGHT"              : 0x27,
    "DOWN"               : 0x28,
    "SELECT"             : 0x29,
    "PRINT"              : 0x2A,
    "EXECUTE"            : 0x2B,
    "SNAPSHOT"           : 0x2C,
    "INSERT"             : 0x2D,
    "DELETE"             : 0x2E,
    "HELP"               : 0x2F,
    "LWIN"               : 0x5B,
    "RWIN"               : 0x5C,
    "APPS"               : 0x5D,
    "SLEEP"              : 0x5F,
    "NUMPAD0"            : 0x60,
    "NUMPAD1"            : 0x61,
    "NUMPAD2"            : 0x62,
    "NUMPAD3"            : 0x63,
    "NUMPAD4"            : 0x64,
    "NUMPAD5"            : 0x65,
    "NUMPAD6"            : 0x66,
    "NUMPAD7"            : 0x67,
    "NUMPAD8"            : 0x68,
    "NUMPAD9"            : 0x69,
    "MULTIPLY"           : 0x6A,
    "ADD"                : 0x6B,
    "SEPARATOR"          : 0x6C,
    "SUBTRACT"           : 0x6D,
    "DECIMAL"            : 0x6E,
    "DIVIDE"             : 0x6F,
    "F1"                 : 0x70,
    "F2"                 : 0x71,
    "F3"                 : 0x72,
    "F4"                 : 0x73,
    "F5"                 : 0x74,
    "F6"                 : 0x75,
    "F7"                 : 0x76,
    "F8"                 : 0x77,
    "F9"                 : 0x78,
    "F10"                : 0x79,
    "F11"                : 0x7A,
    "F12"                : 0x7B,
    "F13"                : 0x7C,
    "F14"                : 0x7D,
    "F15"                : 0x7E,
    "F16"                : 0x7F,
    "F17"                : 0x80,
    "F18"                : 0x81,
    "F19"                : 0x82,
    "F20"                : 0x83,
    "F21"                : 0x84,
    "F22"                : 0x85,
    "F23"                : 0x86,
    "F24"                : 0x87,
    "NUMLOCK"            : 0x90,
    "SCROLL"             : 0x91,
    "OEM_NEC_EQUAL"      : 0x92,
    "OEM_FJ_JISHO"       : 0x92,
    "OEM_FJ_MASSHOU"     : 0x93,
    "OEM_FJ_TOUROKU"     : 0x94,
    "OEM_FJ_LOYA"        : 0x95,
    "OEM_FJ_ROYA"        : 0x96,
    "LSHIFT"             : 0xA0,
    "RSHIFT"             : 0xA1,
    "LCONTROL"           : 0xA2,
    "RCONTROL"           : 0xA3,
    "LMENU"              : 0xA4,
    "RMENU"              : 0xA5,
    "BROWSER_BACK"       : 0xA6,
    "BROWSER_FORWARD"    : 0xA7,
    "BROWSER_REFRESH"    : 0xA8,
    "BROWSER_STOP"       : 0xA9,
    "BROWSER_SEARCH"     : 0xAA,
    "BROWSER_FAVORITES"  : 0xAB,
    "BROWSER_HOME"       : 0xAC,
    "VOLUME_MUTE"        : 0xAD,
    "VOLUME_DOWN"        : 0xAE,
    "VOLUME_UP"          : 0xAF,
    "MEDIA_NEXT_TRACK"   : 0xB0,
    "MEDIA_PREV_TRACK"   : 0xB1,
    "MEDIA_STOP"         : 0xB2,
    "MEDIA_PLAY_PAUSE"   : 0xB3,
    "LAUNCH_MAIL"        : 0xB4,
    "LAUNCH_MEDIA_SELECT": 0xB5,
    "LAUNCH_APP1"        : 0xB6,
    "LAUNCH_APP2"        : 0xB7,
    "OEM_1"              : 0xBA,
    "OEM_PLUS"           : 0xBB,
    "OEM_COMMA"          : 0xBC,
    "OEM_MINUS"          : 0xBD,
    "OEM_PERIOD"         : 0xBE,
    "OEM_2"              : 0xBF,
    "OEM_3"              : 0xC0,
    "OEM_4"              : 0xDB,
    "OEM_5"              : 0xDC,
    "OEM_6"              : 0xDD,
    "OEM_7"              : 0xDE,
    "OEM_8"              : 0xDF,
    "OEM_AX"             : 0xE1,
    "OEM_102"            : 0xE2,
    "ICO_HELP"           : 0xE3,
    "ICO_00"             : 0xE4,
    "PROCESSKEY"         : 0xE5,
    "ICO_CLEAR"          : 0xE6,
    "PACKET"             : 0xE7,
    "OEM_RESET"          : 0xE9,
    "OEM_JUMP"           : 0xEA,
    "OEM_PA1"            : 0xEB,
    "OEM_PA2"            : 0xEC,
    "OEM_PA3"            : 0xED,
    "OEM_WSCTRL"         : 0xEE,
    "OEM_CUSEL"          : 0xEF,
    "OEM_ATTN"           : 0xF0,
    "OEM_FINISH"         : 0xF1,
    "OEM_COPY"           : 0xF2,
    "OEM_AUTO"           : 0xF3,
    "OEM_ENLW"           : 0xF4,
    "OEM_BACKTAB"        : 0xF5,
    "ATTN"               : 0xF6,
    "CRSEL"              : 0xF7,
    "EXSEL"              : 0xF8,
    "EREOF"              : 0xF9,
    "PLAY"               : 0xFA,
    "ZOOM"               : 0xFB,
    "NONAME"             : 0xFC,
    "PA1"                : 0xFD,
    "OEM_CLEAR"          : 0xFE,
}
# fmt: on

vk_dict["HANGEUL"] = vk_dict["KANA"]
vk_dict["HANGUL"] = vk_dict["KANA"]
vk_dict["KANJI"] = vk_dict["HANJA"]
for digit in range(10):
    vk_dict[f"DIGIT{digit}"] = 0x30 + digit
for anum in range(26):
    vk_dict[chr(ord("A") + anum)] = 0x41 + anum
VK = enum("VK", vk_dict.items())
VK_TO_NAME = {vk: name for name, vk in vk_dict.items()}

# fmt: off
VK_TO_KEYNAME = {
    VK.ADD                : "kp_add",
    VK.APPS               : "menu",
    VK.BACK               : "backspace",
    VK.BROWSER_BACK       : "back",
    VK.BROWSER_FAVORITES  : "favorites",
    VK.BROWSER_FORWARD    : "forward",
    VK.BROWSER_HOME       : "homepage",
    VK.BROWSER_HOME       : "www",
    VK.BROWSER_REFRESH    : "refresh",
    VK.BROWSER_SEARCH     : "search",
    VK.BROWSER_STOP       : "stop",
    VK.CANCEL             : "cancel",
    VK.CAPITAL            : "caps_lock",
    VK.CLEAR              : "clear",
    VK.DECIMAL            : "kp_decimal",
    VK.DELETE             : "delete",
    VK.DIVIDE             : "kp_divide",
    VK.DOWN               : "down",
    VK.END                : "end",
    VK.ESCAPE             : "escape",
    VK.EXECUTE            : "execute",
    VK.F1                 : "f1",
    VK.F2                 : "f2",
    VK.F3                 : "f3",
    VK.F4                 : "f4",
    VK.F5                 : "f5",
    VK.F6                 : "f6",
    VK.F7                 : "f7",
    VK.F8                 : "f8",
    VK.F9                 : "f9",
    VK.F10                : "f10",
    VK.F11                : "f11",
    VK.F12                : "f12",
    VK.F13                : "f13",
    VK.F14                : "f14",
    VK.F15                : "f15",
    VK.F16                : "f16",
    VK.F17                : "f17",
    VK.F18                : "f18",
    VK.F19                : "f19",
    VK.F20                : "f20",
    VK.F21                : "f21",
    VK.F22                : "f22",
    VK.F23                : "f23",
    VK.F24                : "f24",
    VK.HELP               : "help",
    VK.HOME               : "home",
    VK.INSERT             : "insert",
    VK.LAUNCH_APP1        : "mycomputer",
    VK.LAUNCH_APP2        : "calculator",
    VK.LAUNCH_MAIL        : "mail",
    VK.LAUNCH_MEDIA_SELECT: "audiomedia",
    VK.LCONTROL           : "control_l",
    VK.LEFT               : "left",
    VK.LMENU              : "alt_l",
    VK.LSHIFT             : "shift_l",
    VK.LWIN               : "super_l",
    VK.MEDIA_NEXT_TRACK   : "audionext",
    VK.MEDIA_PLAY_PAUSE   : "audiopause",
    VK.MEDIA_PLAY_PAUSE   : "audioplay",
    VK.MEDIA_PREV_TRACK   : "audioprev",
    VK.MEDIA_STOP         : "audiostop",
    VK.MODECHANGE         : "mode_switch",
    VK.MULTIPLY           : "kp_multiply",
    VK.NEXT               : "page_down",
    VK.NUMLOCK            : "num_lock",
    VK.NUMPAD0            : "kp_0",
    VK.NUMPAD1            : "kp_1",
    VK.NUMPAD2            : "kp_2",
    VK.NUMPAD3            : "kp_3",
    VK.NUMPAD4            : "kp_4",
    VK.NUMPAD5            : "kp_5",
    VK.NUMPAD6            : "kp_6",
    VK.NUMPAD7            : "kp_7",
    VK.NUMPAD8            : "kp_8",
    VK.NUMPAD9            : "kp_9",
    VK.OEM_PLUS           : "kp_equal",
    VK.PAUSE              : "pause",
    VK.PRIOR              : "page_up",
    VK.RCONTROL           : "control_r",
    VK.RETURN             : "return",
    VK.RIGHT              : "right",
    VK.RMENU              : "alt_r",
    VK.RSHIFT             : "shift_r",
    VK.RWIN               : "super_r",
    VK.SCROLL             : "scroll_lock",
    VK.SELECT             : "select",
    VK.SLEEP              : "standby",
    VK.SNAPSHOT           : "print",
    VK.SUBTRACT           : "kp_subtract",
    VK.TAB                : "tab",
    VK.UP                 : "up",
    VK.VOLUME_DOWN        : "audiolowervolume",
    VK.VOLUME_MUTE        : "audiomute",
    VK.VOLUME_UP          : "audioraisevolume",
}
# fmt: on


def vk_to_str(vk):
    s = VK_TO_NAME.get(vk)
    return f"{vk:x}" if s is None else s


# }}}


DEAD_KEYNAME = {
    "asciicircum": "dead_circumflex",
    "asciitilde": "dead_tilde",
}


class KeyboardLayout:  # {{{
    def __init__(self, layout_id=None, debug=False):
        if layout_id is None:
            layout_id = KeyboardLayout.current_layout_id()
        self.layout_id = layout_id

        # Find virtual key code for each scan code (if any).
        sc_to_vk = {}
        vk_to_sc = {}
        for sc in range(0x01, 0x7F + 1):
            vk = MapVirtualKeyEx(sc, 3, layout_id)
            if vk != 0:
                sc_to_vk[sc] = vk
                vk_to_sc[vk] = sc

        state = (wintypes.BYTE * 256)()
        strbuf = ctypes.create_unicode_buffer(8)

        def fill_state(ss):
            for mod_state, mod_vk in (
                (SHIFT_STATE.SHIFT, VK.SHIFT),
                (SHIFT_STATE.CTRL, VK.CONTROL),
                (SHIFT_STATE.MENU, VK.MENU),
            ):
                state[mod_vk] = 0x80 if (ss & mod_state) != 0 else 0

        def to_unichr(vk, sc, ss):
            fill_state(ss)
            rc = ToUnicodeEx(vk, sc, state, strbuf, len(strbuf), 0, layout_id)
            if rc > 0:
                dead_key = False
                char = ctypes.wstring_at(strbuf.value, rc)
            elif rc < 0:
                # Dead key, flush state.
                dead_key = True
                fill_state(0)
                rc = ToUnicodeEx(
                    VK.SPACE,
                    vk_to_sc[VK.SPACE],
                    state,
                    strbuf,
                    len(strbuf),
                    0,
                    layout_id,
                )
                char = ctypes.wstring_at(strbuf.value, rc) if rc > 0 else ""
            else:
                dead_key = False
                char = ""
            return char, dead_key

        def sort_vk_ss_list(vk_ss_list):
            # Prefer lower modifiers combo.
            return sorted(vk_ss_list, key=lambda vk_ss: popcount_8(vk_ss[1]))

        char_to_vk_ss = defaultdict(list)
        keyname_to_vk = defaultdict(list)

        for sc, vk in sorted(sc_to_vk.items()):
            for ss in SHIFT_STATE:
                if ss in (SHIFT_STATE.MENU, SHIFT_STATE.SHIFT_MENU):
                    # Alt and Shift+Alt don't work, so skip them.
                    continue
                char, dead_key = to_unichr(vk, sc, ss)
                if debug and char:
                    print(
                        "{}{} -> {} [{!r}] {}".format(
                            shift_state_str(ss),
                            vk_to_str(vk),
                            char,
                            char,
                            "[dead key]" if dead_key else "",
                        )
                    )
                kn = None
                if char:
                    kn = CHAR_TO_KEYNAME.get(char)
                    if dead_key:
                        kn = kn and DEAD_KEYNAME.get(kn, "dead_" + kn)
                    else:
                        char_to_vk_ss[char].append((vk, ss))
                    if kn:
                        keyname_to_vk[kn].append((vk, ss))

        self.char_to_vk_ss = {
            char: sort_vk_ss_list(vk_ss_list)[0]
            for char, vk_ss_list in char_to_vk_ss.items()
        }
        self.char_to_vk_ss["\n"] = self.char_to_vk_ss["\r"]

        self.keyname_to_vk = {kn: vk for vk, kn in VK_TO_KEYNAME.items()}
        self.keyname_to_vk.update(
            {
                "next": VK.NEXT,
                "prior": VK.PRIOR,
                "kp_delete": VK.DELETE,
                "kp_enter": VK.RETURN,
                "break": VK.CANCEL,
            }
        )
        self.keyname_to_vk.update(
            {
                kn: sort_vk_ss_list(vk_ss_list)[0][0]
                for kn, vk_ss_list in keyname_to_vk.items()
            }
        )
        add_modifiers_aliases(self.keyname_to_vk)

        self.ss_to_vks = {}
        for ss in SHIFT_STATE:
            vk_list = []
            for mod_state, mod_vk in (
                (SHIFT_STATE.SHIFT, VK.SHIFT),
                (SHIFT_STATE.CTRL, VK.CONTROL),
                (SHIFT_STATE.MENU, VK.MENU),
            ):
                if (ss & mod_state) != 0:
                    vk_list.append(mod_vk)
            self.ss_to_vks[ss] = tuple(vk_list)

    @staticmethod
    def current_layout_id():
        pid = GetWindowThreadProcessId(GetForegroundWindow(), None)
        return GetKeyboardLayout(pid)


# }}}


if __name__ == "__main__":
    sys.stdout = codecs.getwriter("utf8")(sys.stdout)
    layout = KeyboardLayout(debug=True)
    print(f"character to virtual key + shift state [{len(layout.char_to_vk_ss)}]")
    for char, combo in sorted(layout.char_to_vk_ss.items()):
        vk, ss = combo
        print(
            "{} [{!r}:{}] -> {}{}".format(
                char,
                char,
                CHAR_TO_KEYNAME.get(char, "?"),
                shift_state_str(ss),
                vk_to_str(vk),
            )
        )
    print()
    print(f"keyname to virtual key [{len(layout.keyname_to_vk)}]")
    for kn, vk in sorted(layout.keyname_to_vk.items()):
        print(f"{kn} -> {vk_to_str(vk)}")
    print()
    print(f"modifiers combo [{len(layout.ss_to_vks)}]")
    for ss, vk_list in sorted(layout.ss_to_vks.items()):
        print(
            "{} -> {}".format(
                shift_state_str(ss), "+".join(vk_to_str(vk) for vk in vk_list)
            )
        )

# vim: foldmethod=marker
