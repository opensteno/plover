# Copyright (c) 2013 Hesky Fisher
# See LICENSE.txt for details.

"Thread-based monitoring of a stenotype machine using the passport protocol."

from itertools import zip_longest
from typing import ClassVar

from plover.machine.base import SerialStenotypeBase

# Passport protocol is documented here:
# http://www.eclipsecat.com/?q=system/files/Passport%20protocol_0.pdf


class Passport(SerialStenotypeBase):
    """Passport interface."""

    KEYS_LAYOUT = """
        # # # # # # # # # #
        S T P H ~ F N L Y D
        C K W R * Q B G X Z
            A O   E U
        ! ^ +
    """

    SERIAL_PARAMS: ClassVar[dict] = dict(SerialStenotypeBase.SERIAL_PARAMS)
    SERIAL_PARAMS.update(baudrate=38400)

    def __init__(self, params):
        super().__init__(params)
        self.packet = []

    def _read(self, b):
        b = chr(b)
        self.packet.append(b)
        if b == ">":
            self._handle_packet("".join(self.packet))
            del self.packet[:]

    def _handle_packet(self, packet):
        encoded = packet.split("/")[1]
        steno_keys = []
        for key, shadow in grouper(encoded, 2, 0):
            shadow = int(shadow, base=16)
            if shadow >= 8:
                steno_keys.append(key)
        self._notify_keys(steno_keys)

    def run(self):
        """Overrides base class run method. Do not call directly."""
        self._ready()

        while not self.finished.is_set():
            # Grab data from the serial port.
            raw = self.serial_port.read(max(1, self.serial_port.inWaiting()))

            for b in raw:
                self._read(b)


def grouper(iterable, n, fillvalue=None):
    "Collect data into fixed-length chunks or blocks"
    # grouper('ABCDEFG', 3, 'x') --> ABC DEF Gxx
    args = [iter(iterable)] * n
    return zip_longest(*args, fillvalue=fillvalue)
