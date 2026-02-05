"""Thread-based monitoring of a ProCAT stenotype machine."""

import binascii

from plover import log
from plover.machine.base import SerialStenotypeBase


# ProCAT machines send 4 bytes per stroke, with the last byte only consisting of
# FF. So we need only look at the first 3 bytes to see our steno. The leading
# bit is 0.
# fmt: off
STENO_KEY_CHART = (None, "#", "S-", "T-", "K-", "P-", "W-", "H-",
                   "R-", "A-", "O-", "*", "-E", "-U", "-F", "-R",
                   "-P", "-B", "-L", "-G", "-T", "-S", "-D", "-Z",
                   )
# fmt: on

BYTES_PER_STROKE = 4


class ProCat(SerialStenotypeBase):
    """Interface for ProCAT machines."""

    KEYS_LAYOUT = """
        #  #  #  #  #  #  #  #  #  #
        S- T- P- H- * -F -P -L -T -D
        S- K- W- R- * -R -B -G -S -Z
               A- O- -E -U
    """
    KEYMAP_MACHINE_TYPE = "TX Bolt"

    def run(self):
        """Overrides base class run method. Do not call directly."""
        self._ready()
        for packet in self._iter_packets(BYTES_PER_STROKE):
            if (packet[0] & 0x80) or packet[3] != 0xFF:
                log.error("discarding invalid packet: %s", binascii.hexlify(packet))
                continue
            self._notify_keys(self.process_steno_packet(packet))

    @staticmethod
    def process_steno_packet(raw):
        # Raw packet has 4 bytes, we only care about the first 3
        steno_keys = []
        for i, b in enumerate(raw[:3]):
            for j in range(0, 8):
                if b & 0x80 >> j:
                    key = STENO_KEY_CHART[i * 8 + j]
                    steno_keys.append(key)
        return steno_keys
