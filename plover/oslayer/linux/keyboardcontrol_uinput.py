import threading
import os
import selectors

from evdev import (
    UInput,
    ecodes as e,
    util,
    InputDevice,
    list_devices,
    InputEvent,
    KeyEvent,
)
from psutil import process_iter

from plover.oslayer.linux.keyboardlayout_wayland import (
    DEFAULT_LAYOUT,
    GET_WAYLAND_KEYMAP_TIMEOUT_SECONDS,
    HANDLED_EV_KEYCODE_TO_KEY,
    LAYOUTS,
    WAYLAND_AUTO_LAYOUT_NAME,
    KeyCodeInfo,
    generate_plover_keymap_from_xkb_keymap_and_modifiers,
    get_modifier_keycodes,
    ev_keycode_to_xkb_keycode,
    get_wayland_keymap,
)
from plover.output.keyboard import GenericKeyboardEmulation
from plover.machine.keyboard_capture import Capture
from plover.key_combo import parse_key_combo
from plover import log

# EV keycodes of keys considered modifiers when not able to automatically be
# determined from the keymap (this feature isn't implemented yet).
DEFAULT_MODIFIER_EV_KEYCODES: set[int] = {
    e.KEY_LEFTSHIFT,
    e.KEY_RIGHTSHIFT,
    e.KEY_LEFTCTRL,
    e.KEY_RIGHTCTRL,
    e.KEY_LEFTALT,
    e.KEY_RIGHTALT,
    e.KEY_LEFTMETA,
    e.KEY_RIGHTMETA,
}


class KeyboardEmulation(GenericKeyboardEmulation):
    # Map of Plover key name to EV keycode and modifiers
    _key_to_keycodeinfo: dict[str, KeyCodeInfo]
    _can_send_unicode: bool = True

    def __init__(self):
        super().__init__()
        # Initialize UInput with all keys available
        res = util.find_ecodes_by_regex(r"KEY_.*")
        self._ui = UInput(res)

        # Check that ibus or fcitx5 is running
        if not any(p.name() in ["ibus-daemon", "fcitx5"] for p in process_iter()):
            log.warning(
                "It appears that an input method, such as ibus or fcitx5, is not running on your system. Without this, some text may not be output correctly."
            )

        self._key_to_keycodeinfo = {}

    def _update_layout(self, layout):
        if layout == WAYLAND_AUTO_LAYOUT_NAME:
            try:
                keymap = get_wayland_keymap(GET_WAYLAND_KEYMAP_TIMEOUT_SECONDS)
                modifier_index_to_xkb_keycode = get_modifier_keycodes(keymap)

                self._key_to_keycodeinfo = (
                    generate_plover_keymap_from_xkb_keymap_and_modifiers(
                        keymap, modifier_index_to_xkb_keycode
                    )
                )
                log.debug("Retrieved Wayland keymap: %s", self._key_to_keycodeinfo)

                # Verify that no modifier requires modifiers to be pressed in the generated keymap
                modifier_xkb_keycodes = set(
                    keycode
                    for keycodes in modifier_index_to_xkb_keycode
                    for keycode in keycodes
                )
                log.debug(
                    "Modifier index to keycode: %s", modifier_index_to_xkb_keycode
                )
                for key_info in self._key_to_keycodeinfo.values():
                    if (
                        ev_keycode_to_xkb_keycode(key_info.keycode)
                        in modifier_xkb_keycodes
                        and len(key_info.modifiers) > 0
                    ):
                        log.warning(
                            f"Modifier {key_info.keycode} in retrieved Wayland keymap has modifiers itself. Please report this issue."
                        )
            except Exception as e:
                log.error(
                    f"Failed to get Wayland keymap: {e}. Using default layout {DEFAULT_LAYOUT}."
                )
                self._key_to_keycodeinfo = LAYOUTS[DEFAULT_LAYOUT]

            self._can_send_unicode = self._verify_can_send_unicode_key_combo()
            if not self._can_send_unicode:
                log.warning(
                    "At least one key in Ctrl+Shift+U is not available in the current keymap. Unicode input will not be available for special characters not in the keymap."
                )
            return

        if layout not in LAYOUTS:
            log.warning(f"Layout {layout} not supported. Falling back to qwerty.")
        self._key_to_keycodeinfo = LAYOUTS.get(layout, LAYOUTS[DEFAULT_LAYOUT])

    def _get_key(self, key):
        """Helper function to get the keycode and potential modifiers for a key."""
        key_map_info = self._key_to_keycodeinfo.get(key, None)
        if key_map_info is not None:
            return (key_map_info.keycode, key_map_info.modifiers)
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

        # Key press can not be emulated - send unicode symbol instead.
        elif self._can_send_unicode:
            # This check is needed in case the keymap layout (somehow) doesn't have one of ctrl+shift+u mapped, which
            # would cause infinite recursion trying to send one of those keys using the Unicode input.

            # Convert to hex and remove leading "0x"
            unicode_hex = hex(ord(char))[2:]
            self._send_unicode(unicode_hex)
        else:
            log.warning(
                "Cannot send unicode character '%s' - unicode input not available", char
            )

    def _verify_can_send_unicode_key_combo(self) -> bool:
        """Make sure the Unicode starter key combo is mapped (ctrl+shift+u)."""
        if not self._get_key("control_l")[0]:
            return False
        if not self._get_key("shift")[0]:
            return False
        if not self._get_key("u")[0]:
            return False
        return True

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
    # EV keycodes of modifier keys
    _modifier_ev_keycodes: set[int]

    def __init__(self):
        super().__init__()
        self._devices = self._get_devices()

        self._selector = selectors.DefaultSelector()
        self._device_thread = None
        self._device_thread_read_pipe = None
        self._device_thread_write_pipe = None

        res = util.find_ecodes_by_regex(r"KEY_.*")
        self._ui = UInput(res)
        self._suppressed_keys = set()

    def _get_devices(self):
        input_devices = [InputDevice(path) for path in list_devices()]
        keyboard_devices = [dev for dev in input_devices if self._filter_devices(dev)]
        return keyboard_devices

    def _filter_devices(self, device):
        """
        Filter out devices that should not be grabbed and suppressed, to avoid output feeding into itself.
        """
        is_uinput = device.name == "py-evdev-uinput" or device.phys == "py-evdev-uinput"
        # Check for some common keys to make sure it's really a keyboard
        keys = device.capabilities().get(e.EV_KEY, [])
        keyboard_keys_present = any(
            key in keys
            for key in [e.KEY_ESC, e.KEY_SPACE, e.KEY_ENTER, e.KEY_LEFTSHIFT]
        )
        return not is_uinput and keyboard_keys_present

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

    def _run(self):
        keys_pressed_with_modifier: set[int] = set()
        down_modifier_keys: set[int] = set()

        def _parse_key_event(event: InputEvent) -> tuple[str | None, bool]:
            """
            Determine which key Plover should receive due to this event
            and whether the event should be suppressed.
            Considers pressed modifiers and Plover's suppressed keys.
            Returns a tuple of (key_to_send_to_plover, suppress)
            """
            if not self._suppressed_keys:
                # No keys are suppressed
                # Always send to Plover so that it can handle global shortcuts like PLOVER_TOGGLE (PHROLG)
                return HANDLED_EV_KEYCODE_TO_KEY.get(event.code, None), False
            if event.code in DEFAULT_MODIFIER_EV_KEYCODES:
                # Can't use if-else because there is a third case: key_hold
                if event.value == KeyEvent.key_down:
                    down_modifier_keys.add(event.code)
                elif event.value == KeyEvent.key_up:
                    down_modifier_keys.discard(event.code)
                return None, False
            key = HANDLED_EV_KEYCODE_TO_KEY.get(event.code, None)
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
                            key_to_send_to_plover, suppress = _parse_key_event(event)
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
