from dataclasses import dataclass
from typing import Sequence
import string
import contextlib
import mmap
import os
import threading

from xkbcommon import xkb
from evdev import ecodes as e, util

from plover.oslayer.linux.wayland_connection import (
    WaylandConnection,
    wayland_keymap_event_loop,
)


@dataclass
class KeyCodeInfo:
    keycode: int
    # Other keycodes that must be held down with the keycode to send this key
    modifiers: Sequence[int] = ()


# Difference between xkbcommon keycodes and Linux EV keycodes.
# Subtract this value from xkbcommon keycodes to get Linux EV keycodes.
XKB_TO_EV_KEYCODE_OFFSET = 8

VALID_EV_KEYCODES: set[int] = set(util.find_ecodes_by_regex(r"KEY_.*")[1])

WAYLAND_AUTO_LAYOUT_NAME = "wayland-auto"

GET_WAYLAND_KEYMAP_TIMEOUT_SECONDS = 5

# Additional aliases for xkbcommon keysyms to match names in Plover dictionaries.
# Keys beginning with "XF86" are handled as a special case during xkbcommon keymap processing.
# For each xkbcommon keysym, the lowercase of the symbol name is already added to the keymap by the code.
XKB_KEY_NAME_TO_ALIASES: dict[str, list[str]] = {
    "Return": ["\n"],
    "Control_L": ["ctrl", "ctrl_l"],
    "Shift_L": ["shift"],
    "Super_L": ["super", "windows", "command"],
    "Alt_L": ["alt", "option"],
    "Tab": ["\t"],
    "Next": ["page_down"],
    "Prior": ["page_up"],
    "KP_Home": ["kp_7"],
    "KP_Up": ["kp_8"],
    "KP_Prior": ["kp_9"],
    "KP_Left": ["kp_4"],
    "KP_Begin": ["kp_5"],
    "KP_Right": ["kp_6"],
    "KP_End": ["kp_1"],
    "KP_Down": ["kp_2"],
    "KP_Next": ["kp_3"],
    "KP_Insert": ["kp_0"],
    "KP_Delete": ["kp_dot", "kp_decimal"],
}


def xkb_keycode_to_ev_keycode(keycode: int) -> int:
    return keycode - XKB_TO_EV_KEYCODE_OFFSET


def ev_keycode_to_xkb_keycode(keycode: int) -> int:
    return keycode + XKB_TO_EV_KEYCODE_OFFSET


def get_modifier_keycodes(keymap: xkb.Keymap) -> list[list[int]]:
    """
    Returns a list of xkbcommon keycodes for each non-latched and non-locked modifier
    in order of the modifier's index.
    `result[i]` is the list of keycodes for the modifier with index `i`.

    Don't consider latched or locked modifiers (e.g. NumLock)
    because Plover doesn't need to handle those for key combos.
    """
    num_mods = keymap.num_mods()
    modifier_index_to_keycodes: list[list[int]] = [[] for _ in range(num_mods)]

    for keycode in keymap:
        if xkb_keycode_to_ev_keycode(keycode) not in VALID_EV_KEYCODES:
            # Ignore keys that can't be sent or received by evdev
            continue
        # Simulate pressing the key
        keyboard_state = xkb.KeyboardState(keymap)
        key_state = keyboard_state.update_key(keycode, xkb.KeyDirection.XKB_KEY_DOWN)
        # Check if pressing the key depresses a modifier
        is_key_mod = (key_state & xkb.StateComponent.XKB_STATE_MODS_DEPRESSED) and not (
            (key_state & xkb.StateComponent.XKB_STATE_MODS_LOCKED)
            or (key_state & xkb.StateComponent.XKB_STATE_MODS_LATCHED)
        )
        if not is_key_mod:
            continue

        num_layouts = keymap.num_layouts_for_key(keycode)

        for layout in range(0, num_layouts):
            layout_is_active = keyboard_state.layout_index_is_active(
                layout, xkb.StateComponent.XKB_STATE_LAYOUT_EFFECTIVE
            )

            if not layout_is_active:
                continue

            for mod_index in range(num_mods):
                is_mod_active = keyboard_state.mod_index_is_active(
                    mod_index, xkb.StateComponent.XKB_STATE_MODS_DEPRESSED
                )
                if not is_mod_active:
                    continue

                modifier_index_to_keycodes[mod_index].append(keycode)
            # Only consider the first active layout
            break

    return modifier_index_to_keycodes


@contextlib.contextmanager
def fd_context(fd: int):
    try:
        yield fd
    finally:
        os.close(fd)


def get_wayland_keymap(timeout: float) -> xkb.Keymap:
    """Get the current keymap from the default Wayland server"""
    with WaylandConnection() as connection:
        done = False

        def timeout_thread_function():
            import time

            time.sleep(timeout)
            if not done:
                connection.shutdown()

        timeout_thread = threading.Thread(target=timeout_thread_function)
        timeout_thread.start()

        try:
            keymap_fd, keymap_size = wayland_keymap_event_loop(connection)
            done = True
        except InterruptedError:
            raise TimeoutError("Timeout retrieving keymap from Wayland")
    with (
        fd_context(keymap_fd) as keymap_fd,
        mmap.mmap(
            keymap_fd, keymap_size, flags=mmap.MAP_PRIVATE, prot=mmap.PROT_READ
        ) as keymap_file,
    ):
        xkb_context = xkb.Context()
        return xkb_context.keymap_new_from_file(keymap_file)


def generate_plover_keymap_from_xkb_keymap_and_modifiers(
    keymap: xkb.Keymap, modifier_index_to_xkb_keycode: list[list[int]]
) -> dict[str, KeyCodeInfo]:
    """
    Generate a mapping of Plover key names (key names used in Plover dictionary entries) to `KeyCodeInfo`.
    `modifier_index_to_keycode` should be the result of `get_modifier_keycodes`.
    This is a parameter to avoid recomputing the modifier keycodes if they are needed multiple times.
    """
    plover_key_to_keycode: dict[str, KeyCodeInfo] = {}

    layout_index = 0
    for xkb_keycode in iter(keymap):
        try:
            if xkb_keycode_to_ev_keycode(xkb_keycode) not in VALID_EV_KEYCODES:
                # Ignore keys that can't be sent or received by evdev.
                continue
            # Levels are different outputs from the same key with different modifiers pressed.
            level_count = keymap.num_levels_for_key(xkb_keycode, layout_index)

            for level in range(level_count):
                key_syms_for_level = keymap.key_get_syms_by_level(
                    xkb_keycode, layout_index, level
                )
                for key_sym in key_syms_for_level:
                    add_xkb_keysym_to_plover_keymap(
                        xkb_keycode,
                        key_sym,
                        level,
                        keymap,
                        plover_key_to_keycode,
                        layout_index,
                        modifier_index_to_xkb_keycode,
                    )

        except xkb.XKBInvalidKeycode:
            # Iter *should* return only valid, but still returns some invalid...
            pass

    # The "Linefeed" symbol (xkb symbol 0xff0a) has the key string "\n".
    # If Linefeed appears before the enter/return key when iterating over keys in the keymap (which is the case for qwerty), "\n" will be mapped to Linefeed rather than enter.
    # Ensures that "\n" is mapped to the enter/return key instead of Linefeed.
    if "return" in plover_key_to_keycode:
        plover_key_to_keycode["\n"] = plover_key_to_keycode["return"]

    return plover_key_to_keycode


def generate_plover_keymap_from_xkb_keymap(
    keymap: xkb.Keymap,
) -> dict[str, KeyCodeInfo]:
    """
    Wrapper around `generate_plover_keymap_from_xkb_keymap_and_modifiers` that computes the modifiers for you.
    """
    modifier_index_to_keycode = get_modifier_keycodes(keymap)
    return generate_plover_keymap_from_xkb_keymap_and_modifiers(
        keymap, modifier_index_to_keycode
    )


def add_xkb_keysym_to_plover_keymap(
    xkb_keycode: int,
    xkb_keysym: int,
    level: int,
    keymap: xkb.Keymap,
    plover_key_to_keycode: dict[str, KeyCodeInfo],
    layout_index: int,
    modifier_index_to_keycode: list[list[int]],
):
    keysym_name = xkb.keysym_get_name(xkb_keysym)
    keysym_string = xkb.keysym_to_string(xkb_keysym)

    key_modifiers = get_modifiers_for_key_sym(
        keymap, xkb_keycode, layout_index, level, modifier_index_to_keycode
    )

    if keysym_string is not None and keysym_string not in plover_key_to_keycode:
        # Because we iterate levels in order, the lowest level and thus simplest set of modifiers for each symbol is added first.
        # If multiple keys produce the same symbol, only add the first key in iteration order. Same for level_key_name and aliases below.
        plover_key_to_keycode[keysym_string] = KeyCodeInfo(
            xkb_keycode_to_ev_keycode(xkb_keycode), key_modifiers
        )

    for key_alias in XKB_KEY_NAME_TO_ALIASES.get(keysym_name, []):
        if key_alias not in plover_key_to_keycode:
            plover_key_to_keycode[key_alias] = KeyCodeInfo(
                xkb_keycode_to_ev_keycode(xkb_keycode), key_modifiers
            )

    if keysym_name.startswith("XF86"):
        plover_key_name = keysym_name[4:].lower()
        # Add alias with "xf86" for keys starting with "XF86" to be consistent with X11 Plover.
        if plover_key_name not in plover_key_to_keycode:
            plover_key_to_keycode[plover_key_name] = KeyCodeInfo(
                xkb_keycode_to_ev_keycode(xkb_keycode), key_modifiers
            )

    level_key_name_lower = keysym_name.lower()
    if level_key_name_lower not in plover_key_to_keycode:
        plover_key_to_keycode[level_key_name_lower] = KeyCodeInfo(
            xkb_keycode_to_ev_keycode(xkb_keycode), key_modifiers
        )


def get_modifiers_for_key_sym(
    keymap: xkb.Keymap,
    xkb_keycode: int,
    layout_index: int,
    level: int,
    modifier_index_to_keycode: list[list[int]],
) -> list[int]:
    """Get one set of modifiers that are pressed to obtain the given key and level.
    If multiple sets of modifiers produce the same key and level, an arbitrary one is returned."""
    modifier_masks_for_level = keymap.key_get_mods_for_level(
        xkb_keycode, layout_index, level
    )
    key_modifiers: list[int] = []
    # Identify sets of modifiers pressed to obtain the given key and level.
    # Each `mask` is a bitfield of modifiers pressed.
    for mask in modifier_masks_for_level:
        modifier_index = 0
        while mask > 0:
            if mask & 1:
                modifier_keycodes = modifier_index_to_keycode[modifier_index]
                if not modifier_keycodes:
                    # Invalid modifier index. Try the next mask.
                    key_modifiers.clear()
                    break
                key_modifiers.append(xkb_keycode_to_ev_keycode(modifier_keycodes[0]))
            mask >>= 1
            modifier_index += 1
        else:
            # Iterated through all modifiers in a mask and found a valid set.
            break
    return key_modifiers


_context = xkb.Context()

LAYOUTS = {
    "qwerty": generate_plover_keymap_from_xkb_keymap(
        _context.keymap_new_from_names(layout="us")
    ),
    "qwertz": generate_plover_keymap_from_xkb_keymap(
        _context.keymap_new_from_names(layout="de")
    ),
    "dvorak": generate_plover_keymap_from_xkb_keymap(
        _context.keymap_new_from_names(layout="us", variant="dvorak")
    ),
    "colemak": generate_plover_keymap_from_xkb_keymap(
        _context.keymap_new_from_names(layout="us", variant="colemak")
    ),
    "colemak-dh": generate_plover_keymap_from_xkb_keymap(
        _context.keymap_new_from_names(layout="us", variant="colemak_dh")
    ),
}

del _context

DEFAULT_LAYOUT = "qwerty"
assert DEFAULT_LAYOUT in LAYOUTS, "Default layout not in defined layouts"

# Linux EV keycode to Plover key name. Determines which keys can be handled and will be suppressed.
# Many key names are different from xkbcommon, so it's easier to define manually.
HANDLED_EV_KEYCODE_TO_KEY = {
    e.KEY_F1: "F1",
    e.KEY_F2: "F2",
    e.KEY_F3: "F3",
    e.KEY_F4: "F4",
    e.KEY_F5: "F5",
    e.KEY_F6: "F6",
    e.KEY_F7: "F7",
    e.KEY_F8: "F8",
    e.KEY_F9: "F9",
    e.KEY_F10: "F10",
    e.KEY_F11: "F11",
    e.KEY_F12: "F12",
    e.KEY_GRAVE: "`",
    e.KEY_0: "0",
    e.KEY_1: "1",
    e.KEY_2: "2",
    e.KEY_3: "3",
    e.KEY_4: "4",
    e.KEY_5: "5",
    e.KEY_6: "6",
    e.KEY_7: "7",
    e.KEY_8: "8",
    e.KEY_9: "9",
    e.KEY_MINUS: "-",
    e.KEY_EQUAL: "=",
    e.KEY_Q: "q",
    e.KEY_W: "w",
    e.KEY_E: "e",
    e.KEY_R: "r",
    e.KEY_T: "t",
    e.KEY_Y: "y",
    e.KEY_U: "u",
    e.KEY_I: "i",
    e.KEY_O: "o",
    e.KEY_P: "p",
    e.KEY_LEFTBRACE: "[",
    e.KEY_RIGHTBRACE: "]",
    e.KEY_BACKSLASH: "\\",
    e.KEY_A: "a",
    e.KEY_S: "s",
    e.KEY_D: "d",
    e.KEY_F: "f",
    e.KEY_G: "g",
    e.KEY_H: "h",
    e.KEY_J: "j",
    e.KEY_K: "k",
    e.KEY_L: "l",
    e.KEY_SEMICOLON: ";",
    e.KEY_APOSTROPHE: "'",
    e.KEY_Z: "z",
    e.KEY_X: "x",
    e.KEY_C: "c",
    e.KEY_V: "v",
    e.KEY_B: "b",
    e.KEY_N: "n",
    e.KEY_M: "m",
    e.KEY_COMMA: ",",
    e.KEY_DOT: ".",
    e.KEY_SLASH: "/",
    e.KEY_SPACE: "space",
    e.KEY_BACKSPACE: "BackSpace",
    e.KEY_DELETE: "Delete",
    e.KEY_DOWN: "Down",
    e.KEY_END: "End",
    e.KEY_ESC: "Escape",
    e.KEY_HOME: "Home",
    e.KEY_LEFT: "Left",
    e.KEY_PAGEDOWN: "Page_Down",
    e.KEY_PAGEUP: "Page_Up",
    e.KEY_ENTER: "Return",
    e.KEY_RIGHT: "Right",
    e.KEY_TAB: "Tab",
    e.KEY_UP: "Up",
}

# Make sure no keys missing. The last 3 are "\r\x0b\x0c" which don't need to be mapped.
assert all(c in LAYOUTS[DEFAULT_LAYOUT].keys() for c in string.printable[:-3])

if __name__ == "__main__":
    xkb_keymap = get_wayland_keymap(GET_WAYLAND_KEYMAP_TIMEOUT_SECONDS)
    plover_keymap = generate_plover_keymap_from_xkb_keymap(xkb_keymap)
    print("Plover keymap", plover_keymap)
