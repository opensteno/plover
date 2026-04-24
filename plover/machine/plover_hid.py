"""
Thread-based monitoring of a Plover HID stenotype machine.

This implementation is based on the plover-machine-hid plugin created by dnaq (MIT license):
https://github.com/dnaq/plover-machine-hid

Plover HID is a simple HID-based protocol that sends the current state
of the steno machine every time that state changes.
"""

from plover.machine.base import ThreadedStenotypeBase
from plover.misc import boolean
from plover import log

import hid
import time
import platform
import threading
import ctypes
from queue import Queue, Empty
from typing import Any, Dict
from dataclasses import dataclass


def _darwin_disable_exclusive_open() -> None:
    """Disable macOS exclusive HID opens while cython-hidapi lacks a Python API.

    Keep this workaround until https://github.com/trezor/cython-hidapi/issues/178
    is resolved.
    """
    lib_path = getattr(hid, "__file__", None)
    if not lib_path:
        log.warning("hidapi extension path not found; HID may open exclusively")
        return
    try:
        lib = ctypes.CDLL(lib_path)
        func = ctypes.CFUNCTYPE(None, ctypes.c_int)(
            ("hid_darwin_set_open_exclusive", lib)
        )
    except Exception:
        log.warning(
            "failed to load hid_darwin_set_open_exclusive; HID may open exclusively"
        )
        return
    try:
        func(0)
    except Exception:
        log.warning(
            "could not call hid_darwin_set_open_exclusive; HID may open exclusively"
        )


# Invoke once at import time (before any devices are opened)
if platform.system() == "Darwin":
    _darwin_disable_exclusive_open()

USAGE_PAGE: int = 0xFF50
USAGE: int = 0x4C56

N_LEVERS: int = 64

# A simple report contains the report id 1 and one bit
# for each of the 64 buttons in the report.
SIMPLE_REPORT_TYPE: int = 0x01
SIMPLE_REPORT_LEN: int = N_LEVERS // 8

# fmt: off
STENO_KEY_CHART = (
    "S1-", "T-", "K-", "P-", "W-", "H-", "R-", "A-",
    "O-", "*1", "-E", "-U", "-F", "-R", "-P", "-B",
    "-L", "-G", "-T", "-S", "-D", "-Z", "#1", "S2-",
    "*2", "*3", "*4", "#2", "#3", "#4", "#5", "#6",
    "#7", "#8", "#9", "#A", "#B", "#C", "X1", "X2",
    "X3", "X4", "X5", "X6", "X7", "X8", "X9", "X10",
    "X11", "X12", "X13", "X14", "X15", "X16", "X17", "X18",
    "X19", "X20", "X21", "X22", "X23", "X24", "X25", "X26",
)
# fmt: on


class InvalidReport(Exception):
    pass


@dataclass
class HidDeviceRecord:
    device: hid.device
    thread: threading.Thread


class PloverHid(ThreadedStenotypeBase):
    # fmt: off
    KEYS_LAYOUT: str = '''
        #1 #2  #3 #4 #5 #6 #7 #8 #9 #A #B #C
           S1- T- P- H- *1 *3 -F -P -L -T -D
           S2- K- W- R- *2 *4 -R -B -G -S -Z
                  A- O-       -E -U
        X1  X2  X3  X4  X5  X6  X7  X8  X9  X10
        X11 X12 X13 X14 X15 X16 X17 X18 X19 X20
        X21 X22 X23 X24 X25 X26 
    '''
    # fmt: on

    def __init__(self, params: Dict[str, Any]) -> None:
        super().__init__()
        self._params = params
        self._devices: Dict[bytes, HidDeviceRecord] = {}
        self._report_queue: Queue[bytes] = Queue()
        self._lock: threading.Lock = threading.Lock()
        self._device_watcher: threading.Thread | None = None

    def _add_device(self, path: bytes) -> bool:
        """Open a HID device at `path`, start its reader, and mark ready if first."""
        try:
            device = hid.device()
            device.open_path(path)
        except Exception as e:
            log.debug(f"open failed for {path!r}: {e}")
            return False
        was_empty = len(self._devices) == 0
        thread = threading.Thread(
            target=self._read_from_device_loop, args=(path, device), daemon=True
        )
        self._devices[path] = HidDeviceRecord(device=device, thread=thread)
        thread.start()
        if was_empty:
            # We were previously in a disconnected/error state; now we're ready.
            self._ready()
        return True

    def _remove_device(self, path: bytes) -> None:
        """Close and forget a HID device by path; if none remain, mark disconnected."""
        with self._lock:
            entry = self._devices.pop(path, None)
        if not entry:
            return
        device = entry.device
        thread = entry.thread
        # Closing the device will unblock any pending read in the reader thread.
        try:
            device.close()
        except Exception:
            log.debug("failed to close HID device")
            pass
        # Join the reader if we're not currently in that same thread.
        try:
            if thread is not None and thread is not threading.current_thread():
                thread.join(timeout=0.2)
        except Exception:
            log.debug("failed kill device read thread")
            pass
        # If nothing left and we're not shutting down, show Disconnected in the UI
        if not self._devices and not self.finished.is_set():
            self._error()

    def _scan_device_loop(self) -> None:
        """Scan for new matching HID devices and start readers for them."""
        scan_ms = self._params["device_scan_interval_ms"]
        while not self.finished.is_set():
            try:
                paths = [
                    d["path"]
                    for d in hid.enumerate()
                    if (d.get("usage_page") == USAGE_PAGE and d.get("usage") == USAGE)
                ]
            except Exception as e:
                log.debug(f"device scan enumerate failed: {e}")
                paths = []

            with self._lock:
                for path in paths:
                    if path in self._devices:
                        continue
                    # Call outside lock to avoid holding it during open/start
            for path in paths:
                if path in self._devices:
                    continue
                if self._add_device(path):
                    log.debug("device scan: opened new HID device")

            # sleep but wake early if stopping
            if self.finished.wait(scan_ms / 1000.0):
                break

    def _read_from_device_loop(self, path: bytes, device: hid.device) -> None:
        """Per-device reader thread: blocking read, push reports to the report queue."""
        slice_ms = self._params["repeat_interval_ms"]
        while not self.finished.is_set():
            try:
                report = device.read(65536, slice_ms)
            except Exception:
                log.debug("read error: device unplugged?")
                break
            if report:
                try:
                    report_bytes = (
                        report
                        if isinstance(report, (bytes, bytearray))
                        else bytes(report)
                    )
                    self._report_queue.put_nowait(report_bytes)
                except Exception:
                    log.debug("failed to put report in queue")
                    pass
        self._remove_device(path)

    def _parse(self, report: bytes) -> int:
        # The first byte is the report id, and due to idiosyncrasies
        # in how HID-apis work on different operating system we can't
        # map the report id to the contents in a good way, so we force
        # compliant devices to always use a report id of 0x50 ('P').
        if len(report) > SIMPLE_REPORT_LEN and report[0] == 0x50:
            return int.from_bytes(report[1 : SIMPLE_REPORT_LEN + 1], "big")
        else:
            raise InvalidReport()

    def _send(self, key_state: int) -> None:
        steno_actions = self.keymap.keys_to_actions(
            [key for i, key in enumerate(STENO_KEY_CHART) if key_state >> (63 - i) & 1]
        )
        if steno_actions:
            self._notify(steno_actions)

    def run(self) -> None:
        key_state = 0
        current = 0
        last_sent = 0
        press_started = time.time()
        sent_first_up = False
        while not self.finished.wait(0):
            interval_ms = self._params["repeat_interval_ms"]
            try:
                report = self._report_queue.get(timeout=interval_ms / 1000.0)
            except Empty:
                # No report in this slice; handle repeats
                if (
                    self._params["double_tap_repeat"]
                    and 0 != current == last_sent
                    and time.time() - press_started
                    > self._params["repeat_delay_ms"] / 1e3
                ):
                    self._send(current)
                    # Avoid sending an extra chord when the repeated chord is released.
                    sent_first_up = True
                continue

            try:
                current = self._parse(report)
            except InvalidReport:
                log.error("invalid report")
                continue

            press_started = time.time()
            if self._params["first_up_chord_send"]:
                if key_state & ~current and not sent_first_up:
                    # A finger went up: send a first-up chord and remember it.
                    self._send(key_state)
                    last_sent = key_state
                    sent_first_up = True
                if current & ~key_state:
                    # A finger went down: get ready to send a new first-up chord.
                    sent_first_up = False
                key_state = current
            else:
                key_state |= current
                if current == 0:
                    # All fingers are up: send the "total" chord and reset it.
                    self._send(key_state)
                    last_sent = key_state
                    key_state = 0

    def start_capture(self) -> None:
        self.finished.clear()
        self._initializing()
        # Enumerate all hid devices on the machine and if we find one with our
        # usage page and usage we try to connect to it.
        try:
            devices: list[bytes] = [
                device["path"]
                for device in hid.enumerate()
                if device["usage_page"] == USAGE_PAGE and device["usage"] == USAGE
            ]

            if not devices:
                log.info("no HID device found; watching for devices…")
                # setting state to error to display Disconnected in the main window
                self._error()

            for path in devices:
                self._add_device(path)
            # Start device watcher
            self._device_watcher = threading.Thread(
                target=self._scan_device_loop, daemon=True
            )
            self._device_watcher.start()
        except Exception as e:
            self._error()
            log.error(f"error during start of capture: {e}")
            return
        self.start()

    def stop_capture(self) -> None:
        super().stop_capture()
        # Stop device watcher
        t_watch = getattr(self, "_device_watcher", None)
        if t_watch is not None:
            try:
                t_watch.join(timeout=0.3)
            except Exception:
                pass
            self._device_watcher = None
        # Remove all devices via common teardown
        for path in list(self._devices.keys()):
            try:
                self._remove_device(path)
            except Exception:
                pass
        # Drain the report queue best-effort
        try:
            while True:
                self._report_queue.get_nowait()
        except Exception:
            pass

    @classmethod
    def get_option_info(cls):
        return {
            "first_up_chord_send": (False, boolean),
            "double_tap_repeat": (False, boolean),
            "repeat_delay_ms": (200, int),
            "repeat_interval_ms": (30, int),
            "device_scan_interval_ms": (1000, int),
        }
