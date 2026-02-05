# Copyright (c) 2010-2011 Joshua Harlan Lifton.
# See LICENSE.txt for details.

# TODO: add tests for all machines
# TODO: add tests for new status callbacks

"""Base classes for machine types. Do not use directly."""

import binascii
import threading

import serial

from plover import _, log
from plover.machine.keymap import Keymap
from plover.misc import boolean


# i18n: Machine state.
STATE_STOPPED = _("stopped")
# i18n: Machine state.
STATE_INITIALIZING = _("initializing")
# i18n: Machine state.
STATE_RUNNING = _("connected")
# i18n: Machine state.
STATE_ERROR = _("disconnected")


class StenotypeBase:
    """The base class for all Stenotype classes."""

    # Layout of physical keys.
    KEYS_LAYOUT = ""
    # And special actions to map to.
    ACTIONS = ()
    # Fallback to use as machine type for finding a compatible keymap
    # if one is not already available for this machine type.
    KEYMAP_MACHINE_TYPE = None

    def __init__(self):
        # Setup default keymap with no translation of keys.
        keys = self.get_keys()
        self.keymap = Keymap(keys, keys)
        self.keymap.set_mappings(zip(keys, keys))
        self.stroke_subscribers = []
        self.state_subscribers = []
        self.state = STATE_STOPPED

    def set_keymap(self, keymap):
        """Setup machine keymap."""
        self.keymap = keymap

    def start_capture(self):
        """Begin listening for output from the stenotype machine."""
        pass

    def stop_capture(self):
        """Stop listening for output from the stenotype machine."""
        pass

    def add_stroke_callback(self, callback):
        """Subscribe to output from the stenotype machine.

        Argument:

        callback -- The function to call whenever there is output from
        the stenotype machine and output is being captured.

        """
        self.stroke_subscribers.append(callback)

    def remove_stroke_callback(self, callback):
        """Unsubscribe from output from the stenotype machine.

        Argument:

        callback -- A function that was previously subscribed.

        """
        self.stroke_subscribers.remove(callback)

    def add_state_callback(self, callback):
        self.state_subscribers.append(callback)

    def remove_state_callback(self, callback):
        self.state_subscribers.remove(callback)

    def _notify(self, steno_keys):
        """Invoke the callback of each subscriber with the given argument."""
        for callback in self.stroke_subscribers:
            callback(steno_keys)

    def _notify_keys(self, steno_keys):
        steno_keys = self.keymap.keys_to_actions(steno_keys)
        if steno_keys:
            self._notify(steno_keys)

    def set_suppression(self, enabled):
        """Enable keyboard suppression.

        This is only of use for the keyboard machine,
        to suppress the keyboard when then engine is running.
        """
        pass

    def suppress_last_stroke(self, send_backspaces):
        """Suppress the last stroke key events after the fact.

        This is only of use for the keyboard machine,
        and the engine is resumed with a command stroke.

        Argument:

        send_backspaces -- The function to use to send backspaces.
        """
        pass

    def _set_state(self, state):
        self.state = state
        for callback in self.state_subscribers:
            callback(state)

    def _stopped(self):
        self._set_state(STATE_STOPPED)

    def _initializing(self):
        self._set_state(STATE_INITIALIZING)

    def _ready(self):
        self._set_state(STATE_RUNNING)

    def _error(self):
        self._set_state(STATE_ERROR)

    @classmethod
    def get_actions(cls):
        """List of supported actions to map to."""
        return cls.ACTIONS

    @classmethod
    def get_keys(cls):
        return tuple(cls.KEYS_LAYOUT.split())

    @classmethod
    def get_option_info(cls):
        """Get the default options for this machine."""
        return {}


class ThreadedStenotypeBase(StenotypeBase, threading.Thread):
    """Base class for thread based machines.

    Subclasses should override run.
    """

    def __init__(self):
        threading.Thread.__init__(self)
        self._on_unhandled_exception(self._error)
        self.name += "-machine"
        StenotypeBase.__init__(self)
        self.finished = threading.Event()

    def _on_unhandled_exception(self, action):
        super_invoke_excepthook = self._invoke_excepthook

        def invoke_excepthook(self):
            action()
            super_invoke_excepthook(self)

        self._invoke_excepthook = invoke_excepthook

    def run(self):
        """This method should be overridden by a subclass."""
        pass

    def start_capture(self):
        """Begin listening for output from the stenotype machine."""
        self.finished.clear()
        self._initializing()
        self.start()

    def stop_capture(self):
        """Stop listening for output from the stenotype machine."""
        self.finished.set()
        try:
            self.join()
        except RuntimeError:
            pass
        self._stopped()


class SerialStenotypeBase(ThreadedStenotypeBase):
    """For use with stenotype machines that connect via serial port.

    This class implements the three methods necessary for a standard
    stenotype interface: start_capture, stop_capture, and
    add_callback.

    """

    # Default serial parameters.
    SERIAL_PARAMS = {
        "port": None,
        "baudrate": 9600,
        "bytesize": 8,
        "parity": "N",
        "stopbits": 1,
        "timeout": 2.0,
    }

    def __init__(self, serial_params):
        """Monitor the stenotype over a serial port.

        The key-value pairs in the <serial_params> dict are the same
        as the keyword arguments for a serial.Serial object.

        """
        ThreadedStenotypeBase.__init__(self)
        self._on_unhandled_exception(self._handle_disconnect)
        self.serial_port = None
        self.serial_params = serial_params

    def _close_port(self):
        if self.serial_port is None:
            return
        self.serial_port.close()
        self.serial_port = None

    def _handle_disconnect(self):
        self._close_port()
        self._error()

    def start_capture(self):
        self._close_port()

        try:
            self.serial_port = serial.Serial(**self.serial_params)
        except (serial.SerialException, OSError):
            log.warning("Can't open serial port", exc_info=True)
            self._error()
            return

        if not self.serial_port.isOpen():
            log.warning("Serial port is not open: %s", self.serial_params.get("port"))
            self._error()
            return

        return ThreadedStenotypeBase.start_capture(self)

    def stop_capture(self):
        """Stop listening for output from the stenotype machine."""
        ThreadedStenotypeBase.stop_capture(self)
        self._close_port()

    @classmethod
    def get_option_info(cls):
        """Get the default options for this machine."""

        def sb(s):
            return int(float(s)) if float(s).is_integer() else float(s)

        converters = {
            "port": str,
            "baudrate": int,
            "bytesize": int,
            "parity": str,
            "stopbits": sb,
            "timeout": float,
            "xonxoff": boolean,
            "rtscts": boolean,
        }
        return {
            setting: (default, converters[setting])
            for setting, default in cls.SERIAL_PARAMS.items()
        }

    def _iter_packets(self, packet_size):
        """Yield packets of <packets_size> bytes until the machine is stopped.

        N.B.: to workaround the fact that the Toshiba Bluetooth stack
        on Windows does not correctly handle the read timeout setting
        (returning immediately if some data is already available):
        - the effective timeout is re-configured to <timeout/packet_size>
        - multiple reads are  done (until a packet is complete)
        - an incomplete packet will only be discarded if one of
          those reads return no data (but not on short read)
        """
        if not self.serial_port:
            log.warning("Serial port not initialized")
            return

        configured_timeout = self.serial_params.get(
            "timeout", self.SERIAL_PARAMS["timeout"]
        )
        self.serial_port.timeout = max(
            configured_timeout / packet_size,
            0.01,
        )
        packet = b""
        while not self.finished.is_set():
            raw = self.serial_port.read(packet_size - len(packet))
            if not raw:
                if packet:
                    log.error(
                        "discarding incomplete packet: %s", binascii.hexlify(packet)
                    )
                packet = b""
                continue
            packet += raw
            if len(packet) != packet_size:
                continue
            yield packet
            packet = b""
