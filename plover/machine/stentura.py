# Copyright (c) 2011 Hesky Fisher
# See LICENSE.txt for details.
# Many thanks to a steno geek for help with the protocol.

import struct

from plover import log
import plover.machine.base

# TODO: Come up with a mechanism to communicate back to the engine when there
# is a connection error.
# TODO: Address any generic exceptions still left.

"""Thread-based monitoring of a stenotype machine using the stentura protocol."""

"""
The stentura protocol uses packets to communicate with the machine. A
request packet is sent to the machine and a response packet is received. If
no response is received after a one second timeout then the same packet
should be sent again. The machine may hold off on responding to a READC
packet for up to 500ms if there are no new strokes.

Each request packet should have a sequence number that is one higher than
the previously sent packet modulo 256. The response packet will have the
same sequence number. Each packet consists of a header followed by an
optional data section. All multibyte fields are little endian.

The request packet header is structured as follows:
- SOH: 1 byte. Always set to ASCII SOH (0x1).
- seq: 1 byte. The sequence number of this packet.
- length: 2 bytes. The total length of the packet, including the data
  section, in bytes.
- action: 2 bytes. The action requested. See actions below.
- p1: 2 bytes. Parameter 1. The values for the parameters depend on the
  action.
- p2: 2 bytes. Parameter 2.
- p3: 2 bytes. Parameter 3.
- p4: 2 bytes. Parameter 4.
- p5: 2 bytes. Parameter 5.
- checksum: 2 bytes. The CRC is computed over the packet from seq through
  p5. The specific CRC algorithm used is described above in the Crc class.

The request header can be followed by a data section. The meaning of the
data section depends on the action:
- data: variable length.
- crc: 2 bytes. A CRC over just the data section.

The response packet header is structured as follows:
- SOH: 1 byte. Always set to ASCII SOH (0x1).
- seq: 1 byte. The sequence number of the request packet.
- length: 2 bytes. The total length of the packet, including the data
  section, in bytes.
- action: 2 bytes. The action of the request packet.
- error: 2 bytes. The error code. Zero if no error.
- p1: 2 bytes. Parameter 1. The values of the parameters depend on the
  action.
- p2: 2 bytes. Parameter 2.
- checksum: 2 bytes. The CRC is computed over the packet from seq through
  p2.

The response header can be follows by a data section, whose meaning is
dependent on the action. The structure is the same as in request packets.

The stentura machine has a concept of drives and files. The first (and
possibly only) drive is called A. Each file consists of a set of one or
more blocks. Each block is 512 bytes long.

In addition to regular files, there is a realtime file whose name is
'REALTIME.000'. All strokes typed are appended to this file. Subsequent
reads from the realtime file ignore positional arguments and only return
all the strokes since the last read action. However, opening the file again
and reading from the beginning will result in all the same strokes being
read again. The only reliable way to jump to the end is to do a full,
sequential, read to the end before processing any strokes. I'm told that on
some machines sending a READC without an OPEN will just read from the
realtime file.

The contents of the files are a sequence of strokes. Each stroke consists
of four bytes. Each byte has the two most significant bytes set to one. The
rest of the byte is a bitmask indicating which keys were pressed during the
stroke. The format is as follows: 11^#STKP 11WHRAO* 11EUFRPB 11LGTSDZ ^ is
something called a stenomark. I'm not sure what that is. # is the number
bar.

Note: Only OPEN and READC are needed to get strokes as they are typed from
the realtime file.

Actions and their packets:

All unmentioned parameters should be zero and unless explicitly mentioned
the packet should have no data section.

RESET (0x14):
Unknown.

DISKSTATUS (0x7):
Unknown.
p1 is set to the ASCII value corresponding to the drive letter, e.g. 'A'.

GETDOS (0x18):
Returns the DOS filenames for the files in the requested drive.
p1 is set to the ASCII value corresponding to the drive letter, e.g. 'A'.
p2 is set to one to return the name of the realtime file (which is always
'REALTIME.000').
p3 controls which page to return, with 20 filenames per page.
The return packet contains a data section that is 512 bytes long. The first
bytes seems to be one. The filename for the first file starts at offset 32.
My guess would be that the other filenames would exist at a fixed offset of
24 bytes apart. So first filename is at 32, second is at 56, third at 80,
etc. There seems to be some meta data stored after the filename but I don't
know what it means.

DELETE (0x3):
Deletes the specified files. NOP on realtime file.
p1 is set to the ASCII value corresponding to the drive letter, e.g. 'A'.
The filename is specified in the data section.

OPEN (0xA):
Opens a file for reading. This action is sticky and causes this file to be
the current file for all following READC packets.
p1 is set to the ASCII value corresponding to the drive letter, e.g. 'A'.
The filename is specified in the data section.
I'm told that if there is an error opening the realtime file then no
strokes have been written yet.
TODO: Check that and implement workaround.

READC (0xB):
Reads characters from the currently opened file.
p1 is set to 1, I'm not sure why.
p3 is set to the maximum number of bytes to read but should probably be
512.
p4 is set to the block number.
p5 is set to the starting byte offset within the block.
It's possible that the machine will ignore the positional arguments to
READC when reading from the realtime file and just return successive values
for each call.
The response will have the number of bytes read in p1 (but the same is
deducible from the length). The data section will have the contents read
from the file.

CLOSE (0x2):
Closes the current file.
p1 is set to one, I don't know why.

TERM (0x15):
Unknown.

DIAG (0x19):
Unknown.

"""


# Python 3 replacement for Python 2 buffer.
def buffer(object, offset=None, size=None):
    if offset is None:
        offset = 0
    if size is None:
        size = len(object) - offset
    return memoryview(object)[offset : offset + size]


def _allocate_buffer():
    return bytearray(1024)


class _ProtocolViolationException(Exception):
    """Something has happened that is doesn't follow the protocol."""

    pass


class _StopException(Exception):
    """The thread was asked to stop."""

    pass


class _TimeoutException(Exception):
    """An operation has timed out."""

    pass


class _ConnectionLostException(Exception):
    """Cannot communicate with the machine."""

    pass


# fmt: off
_CRC_TABLE = [
    0x0000, 0xc0c1, 0xc181, 0x0140, 0xc301, 0x03c0, 0x0280, 0xc241,
    0xc601, 0x06c0, 0x0780, 0xc741, 0x0500, 0xc5c1, 0xc481, 0x0440,
    0xcc01, 0x0cc0, 0x0d80, 0xcd41, 0x0f00, 0xcfc1, 0xce81, 0x0e40,
    0x0a00, 0xcac1, 0xcb81, 0x0b40, 0xc901, 0x09c0, 0x0880, 0xc841,
    0xd801, 0x18c0, 0x1980, 0xd941, 0x1b00, 0xdbc1, 0xda81, 0x1a40,
    0x1e00, 0xdec1, 0xdf81, 0x1f40, 0xdd01, 0x1dc0, 0x1c80, 0xdc41,
    0x1400, 0xd4c1, 0xd581, 0x1540, 0xd701, 0x17c0, 0x1680, 0xd641,
    0xd201, 0x12c0, 0x1380, 0xd341, 0x1100, 0xd1c1, 0xd081, 0x1040,
    0xf001, 0x30c0, 0x3180, 0xf141, 0x3300, 0xf3c1, 0xf281, 0x3240,
    0x3600, 0xf6c1, 0xf781, 0x3740, 0xf501, 0x35c0, 0x3480, 0xf441,
    0x3c00, 0xfcc1, 0xfd81, 0x3d40, 0xff01, 0x3fc0, 0x3e80, 0xfe41,
    0xfa01, 0x3ac0, 0x3b80, 0xfb41, 0x3900, 0xf9c1, 0xf881, 0x3840,
    0x2800, 0xe8c1, 0xe981, 0x2940, 0xeb01, 0x2bc0, 0x2a80, 0xea41,
    0xee01, 0x2ec0, 0x2f80, 0xef41, 0x2d00, 0xedc1, 0xec81, 0x2c40,
    0xe401, 0x24c0, 0x2580, 0xe541, 0x2700, 0xe7c1, 0xe681, 0x2640,
    0x2200, 0xe2c1, 0xe381, 0x2340, 0xe101, 0x21c0, 0x2080, 0xe041,
    0xa001, 0x60c0, 0x6180, 0xa141, 0x6300, 0xa3c1, 0xa281, 0x6240,
    0x6600, 0xa6c1, 0xa781, 0x6740, 0xa501, 0x65c0, 0x6480, 0xa441,
    0x6c00, 0xacc1, 0xad81, 0x6d40, 0xaf01, 0x6fc0, 0x6e80, 0xae41,
    0xaa01, 0x6ac0, 0x6b80, 0xab41, 0x6900, 0xa9c1, 0xa881, 0x6840,
    0x7800, 0xb8c1, 0xb981, 0x7940, 0xbb01, 0x7bc0, 0x7a80, 0xba41,
    0xbe01, 0x7ec0, 0x7f80, 0xbf41, 0x7d00, 0xbdc1, 0xbc81, 0x7c40,
    0xb401, 0x74c0, 0x7580, 0xb541, 0x7700, 0xb7c1, 0xb681, 0x7640,
    0x7200, 0xb2c1, 0xb381, 0x7340, 0xb101, 0x71c0, 0x7080, 0xb041,
    0x5000, 0x90c1, 0x9181, 0x5140, 0x9301, 0x53c0, 0x5280, 0x9241,
    0x9601, 0x56c0, 0x5780, 0x9741, 0x5500, 0x95c1, 0x9481, 0x5440,
    0x9c01, 0x5cc0, 0x5d80, 0x9d41, 0x5f00, 0x9fc1, 0x9e81, 0x5e40,
    0x5a00, 0x9ac1, 0x9b81, 0x5b40, 0x9901, 0x59c0, 0x5880, 0x9841,
    0x8801, 0x48c0, 0x4980, 0x8941, 0x4b00, 0x8bc1, 0x8a81, 0x4a40,
    0x4e00, 0x8ec1, 0x8f81, 0x4f40, 0x8d01, 0x4dc0, 0x4c80, 0x8c41,
    0x4400, 0x84c1, 0x8581, 0x4540, 0x8701, 0x47c0, 0x4680, 0x8641,
    0x8201, 0x42c0, 0x4380, 0x8341, 0x4100, 0x81c1, 0x8081, 0x4040
]
# fmt: on


def _crc(data, offset=None, size=None):
    """Compute the Crc algorithm used by the stentura protocol.

    This algorithm is described by the Rocksoft^TM Model CRC Algorithm as
    follows:

    Name   : "CRC-16"
    Width  : 16
    Poly   : 8005
    Init   : 0000
    RefIn  : True
    RefOut : True
    XorOut : 0000
    Check  : BB3D

    Args:
    - data: The data to checksum. The data should be an iterable that returns
            bytes

    Returns: The computed crc for the data.

    """
    if offset is None:
        offset = 0
    if size is None:
        size = len(data) - offset
    checksum = 0
    for n in range(offset, offset + size):
        b = data[n]
        checksum = _CRC_TABLE[(checksum ^ b) & 0xFF] ^ ((checksum >> 8) & 0xFF)
    return checksum


def _write_to_buffer(buf, offset, data):
    """Write data to buf at offset.

    Note: buf must be big enough, and will not be extended as needed.

    Args:
    - buf: The buffer. Should be of type bytearray()
    - offset. The offset at which to start writing.
    - data: An iterable containing the data to write.
    """
    buf[offset : offset + len(data)] = data


# Helper table for parsing strokes of the form:
# 11^#STKP 11WHRAO* 11EUFRPB 11LGTSDZ
# fmt: off
_STENO_KEY_CHART = ("^", "#", "S-", "T-", "K-", "P-",    # Byte #1
                    "W-", "H-", "R-", "A-", "O-", "*",   # Byte #2
                    "-E", "-U", "-F", "-R", "-P", "-B",  # Byte #3
                    "-L", "-G", "-T", "-S", "-D", "-Z")  # Byte #4
# fmt: on


def _parse_stroke(a, b, c, d):
    """Parse a stroke and return a list of keys pressed.

    Args:
    - a: The first byte.
    - b: The second byte.
    - c: The third byte.
    - d: The fourth byte.

    Returns: A sequence with all the keys pressed in the stroke.
             e.g. ['S-', 'A-', '-T']

    """
    fullstroke = ((a & 0x3F) << 18) | ((b & 0x3F) << 12) | ((c & 0x3F) << 6) | d & 0x3F
    return [_STENO_KEY_CHART[i] for i in range(24) if (fullstroke & (1 << (23 - i)))]


def _parse_strokes(data):
    """Parse strokes from a buffer and return a sequence of strokes.

    Args:
    - data: A byte buffer.

    Returns: A sequence of strokes. Each stroke is a sequence of pressed keys.

    Throws:
    - _ProtocolViolationException if the data doesn't follow the protocol.

    """
    strokes = []
    if (len(data) % 4) != 0:
        raise _ProtocolViolationException(
            "Data size is not divisible by 4: %d" % (len(data))
        )
    for b in data:
        if (b & 0b11000000) != 0b11000000:
            raise _ProtocolViolationException("Data is not stroke: 0x%X" % (b))
    for a, b, c, d in zip(*([iter(data)] * 4)):
        strokes.append(_parse_stroke(a, b, c, d))
    return strokes


# Actions
_CLOSE = 0x2
_DELETE = 0x3
_DIAG = 0x19
_DISKSTATUS = 0x7
_GETDOS = 0x18
_OPEN = 0xA
_READC = 0xB
_RESET = 0x14
_TERM = 0x15

# Compiled struct for writing request headers.
_REQUEST_STRUCT = struct.Struct("<2B7H")
_SHORT_STRUCT = struct.Struct("<H")


def _make_request(buf, action, seq, p1=0, p2=0, p3=0, p4=0, p5=0, data=None):
    """Create a request packet.

    Args:
    - buf: The buffer used for the packet. Should be bytearray() and big
    enough, as it will not be extended as needed.
    - action: The action for the packet.
    - seq: The sequence numbe for the packet.
    - p1 - p5: Parameter N for the packet (default: 0).
    - data: The data to add to the packet as a sequence of bytes, if any
    (default: None).

    Returns: A buffer as a slice of the passed in buf that holds the packet.

    """
    length = 18
    if data:
        length += len(data) + 2  # +2 for the data CRC.
    _REQUEST_STRUCT.pack_into(buf, 0, 1, seq, length, action, p1, p2, p3, p4, p5)
    crc = _crc(buf, 1, 15)
    _SHORT_STRUCT.pack_into(buf, 16, crc)
    if data:
        _write_to_buffer(buf, 18, data)
        crc = _crc(data)
        _SHORT_STRUCT.pack_into(buf, length - 2, crc)
    return buffer(buf, 0, length)


def _make_open(buf, seq, drive, filename):
    """Make a packet with the OPEN command.

    Args:
    - buf: The buffer to use of type bytearray(). Will be extended if
    needed.
    - seq: The sequence number of the packet.
    - drive: The letter of the drive (probably 'A').
    - filename: The name of the file (probably 'REALTIME.000').

    Returns: A buffer as a slice of the passed in buf that holds the packet.

    """
    return _make_request(buf, _OPEN, seq, p1=ord(drive), data=filename)


def _make_read(buf, seq, block, byte, length=512):
    """Make a packet with the READC command.

    Args:
    - buf: The buffer to use of type bytearray(). Will be extended if
    needed.
    - seq: The sequence number of the packet.
    - block: The index of the file block to read.
    - byte: The byte offset within the block at which to start reading.
    - length: The number of bytes to read, max 512 (default: 512).

    Returns: A buffer as a slice of the passed in buf that holds the packet.

    """
    return _make_request(buf, _READC, seq, p1=1, p3=length, p4=block, p5=byte)


def _make_reset(buf, seq):
    """Make a packet with the RESET command.

    Args:
    - buf: The buffer to use of type bytearray(). Will be extended if
    needed.
    - seq: The sequence number of the packet.

    Returns: A buffer as a slice of the passed in buf that holds the packet.

    """
    return _make_request(buf, _RESET, seq)


def _validate_response(packet):
    """Validate a response packet.

    Args:
    - packet: The packet to validate.

    Returns: True if the packet is valid, False otherwise.

    """
    if len(packet) < 14:
        return False
    length = _SHORT_STRUCT.unpack(packet[2:4])[0]
    if length != len(packet):
        return False
    if _crc(packet, 1, 13) != 0:
        return False
    if length > 14:
        if length < 17:
            return False
        if _crc(packet, 14) != 0:
            return False
    return True


def _read_data(port, stop, buf, offset, num_bytes):
    """Read data off the serial port and into port at offset.

    Args:
    - port: The serial port to read.
    - stop: An event which, when set, causes this function to stop.
    - buf: The buffer to write.
    - offset: The offset into the buffer to write.
    - num_bytes: The number of bytes expected

    Returns: The number of bytes read.

    Raises:
    _StopException: If stop is set.
    _TimeoutException: If the timeout is reached with no data read.

    """

    assert num_bytes > 0
    read_bytes = port.read(num_bytes)
    if stop.is_set():
        raise _StopException()
    if num_bytes > len(read_bytes):
        raise _TimeoutException()
    _write_to_buffer(buf, offset, read_bytes)
    return len(read_bytes)


MINIMUM_PACKET_LENGTH = 14


def _read_packet(port, stop, buf):
    """Read a full packet from the port.

    Reads from the port until a full packet is received or the stop or timeout
    conditions are met.

    Args:
    - port: The port to read.
    - stop: Event object used to request stopping.
    - buf: The buffer to write.

    Returns: A buffer as a slice of buf holding the packet.

    Raises:
    _ProtocolViolationException: If the packet doesn't conform to the protocol.
    _TimeoutException: If the packet is not read within the timeout.
    _StopException: If a stop was requested.

    """
    bytes_read = 0
    bytes_read += _read_data(port, stop, buf, bytes_read, 4)
    assert 4 == bytes_read
    packet_length = _SHORT_STRUCT.unpack_from(buf, 2)[0]
    # Packet length should always be at least 14 bytes long
    if packet_length < MINIMUM_PACKET_LENGTH:
        raise _ProtocolViolationException()
    bytes_read += _read_data(port, stop, buf, bytes_read, packet_length - bytes_read)
    packet = buffer(buf, 0, bytes_read)
    if not _validate_response(packet):
        raise _ProtocolViolationException()
    return buffer(buf, 0, bytes_read)


def _write_to_port(port, data):
    """Write data to a port.

    Args:
    - port: The port to write.
    - data: The data to write

    """
    while data:
        data = buffer(data, port.write(data))


def _send_receive(port, stop, packet, buf, max_tries=3):
    """Send a packet and return the response.

    Send a packet and make sure there is a response and it is for the correct
    request and return it, otherwise retry max_retries times.

    Args:
    - port: The port to read.
    - stop: Event used to signal tp stop.
    - packet: The packet to send. May be used after buf is written so should be
    distinct.
    - buf: Buffer used to store response.
    - max_tries: The maximum number of times to retry sending the packet and
    reading the response before giving up (default: 3).

    Returns: A buffer as a slice of buf holding the response packet.

    Raises:
    _ConnectionLostException: If we can't seem to talk to the machine.
    _StopException: If a stop was requested.
    _ProtocolViolationException: If the responses packet violates the protocol.

    """
    request_action = _SHORT_STRUCT.unpack(packet[4:6])[0]
    for attempt in range(max_tries):
        _write_to_port(port, packet)
        try:
            response = _read_packet(port, stop, buf)
            if response[1] != packet[1]:
                continue  # Wrong sequence number.
            response_action = _SHORT_STRUCT.unpack(response[4:6])[0]
            if request_action != response_action:
                raise _ProtocolViolationException()
            return response
        except _TimeoutException:
            continue
    raise _ConnectionLostException()


class _SequenceCounter:
    """A mod 256 counter."""

    def __init__(self, seq=0):
        """Init a new counter starting at seq."""
        self.seq = seq

    def __call__(self):
        """Return the next value."""
        cur, self.seq = self.seq, (self.seq + 1) % 256
        return cur


def _read(port, stop, seq, request_buf, response_buf, stroke_buf, block, byte):
    """Read the full contents of the current file from beginning to end.

    The file should be opened first.

    Args:
    - port: The port to use.
    - stop: The event used to request stopping.
    - seq: A _SequenceCounter instance to use to track packets.
    - request_buf: Buffer to use for request packet.
    - response_buf: Buffer to use for response packet.
    - stroke_buf: Buffer to use for strokes read from the file.

    Raises:
    _ProtocolViolationException: If the protocol is violated.
    _StopException: If a stop is requested.
    _ConnectionLostException: If we can't seem to talk to the machine.

    """
    bytes_read = 0
    while True:
        packet = _make_read(request_buf, seq(), block, byte, length=512)
        response = _send_receive(port, stop, packet, response_buf)
        p1 = _SHORT_STRUCT.unpack(response[8:10])[0]
        if not (
            (p1 == 0 and len(response) == 14)  # No data.
            or (p1 == len(response) - 16)
        ):  # Data.
            raise _ProtocolViolationException()
        if p1 == 0:
            return block, byte, buffer(stroke_buf, 0, bytes_read)
        data = buffer(response, 14, p1)
        _write_to_buffer(stroke_buf, bytes_read, data)
        bytes_read += len(data)
        byte += p1
        if byte >= 512:
            block += 1
            byte -= 512


def _loop(port, stop, callback, ready_callback, timeout=1):
    """Enter into a loop talking to the machine and returning strokes.

    Args:
    - port: The port to use.
    - stop: The event used to signal that it's time to stop.
    - callback: A function that takes a list of pressed keys, called for each
    stroke.
    - ready_callback: A function that is called when the machine is ready.
    - timeout: Timeout to use when waiting for a response in seconds. Should be
    1 when talking to a real machine. (default: 1)

    Raises:
    _ProtocolViolationException: If the protocol is violated.
    _StopException: If a stop is requested.
    _ConnectionLostException: If we can't seem to talk to the machine.

    """
    # We want to give the machine a standard timeout to finish whatever it's
    # doing but we also want to stop if asked to so this is the safe way to
    # wait.
    if stop.wait(timeout):
        raise _StopException()
    port.flushInput()
    port.flushOutput()
    # Set serial port timeout to the timeout value
    port.timeout = timeout
    # With Python 3, our replacement for buffer(), using memoryview, does not
    # allow resizing the original bytearray(), so make sure our buffers are big
    # enough to begin with.
    request_buf, response_buf = _allocate_buffer(), _allocate_buffer()
    stroke_buf = _allocate_buffer()
    seq = _SequenceCounter()
    request = _make_open(request_buf, seq(), b"A", b"REALTIME.000")
    # Any checking needed on the response packet?
    _send_receive(port, stop, request, response_buf)
    # Do a full read to get to the current position in the realtime file.
    block, byte = 0, 0
    block, byte, _ = _read(
        port, stop, seq, request_buf, response_buf, stroke_buf, block, byte
    )
    ready_callback()
    while True:
        block, byte, data = _read(
            port, stop, seq, request_buf, response_buf, stroke_buf, block, byte
        )
        strokes = _parse_strokes(data)
        for stroke in strokes:
            callback(stroke)


class Stentura(plover.machine.base.SerialStenotypeBase):
    """Stentura interface.

    This class implements the three methods necessary for a standard
    stenotype interface: start_capture, stop_capture, and
    add_callback.
    """

    KEYS_LAYOUT = """
        #  #  #  #  #  #  #  #  #  #
        S- T- P- H- * -F -P -L -T -D
        S- K- W- R- * -R -B -G -S -Z
              A- O-   -E -U
        ^
    """

    def run(self):
        """Overrides base class run method. Do not call directly."""
        try:
            _loop(self.serial_port, self.finished, self._notify_keys, self._ready)
        except _StopException:
            pass
        except Exception:
            log.info("Failure starting Stentura", exc_info=True)
            self._error()
