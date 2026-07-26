# Copyright (c) 2011 Hesky Fisher
# See LICENSE.txt for details.

"""Unit tests for stentura.py."""

import struct
import threading

import pytest

from plover.machine import stentura


def make_response(seq, action, error=0, p1=0, p2=0, data=None, length=None):
    if not length:
        length = 14
        if data:
            length += 2 + len(data)
    response = bytearray(14 + ((2 + len(data)) if data else 0))
    struct.pack_into("<2B5H", response, 0, 1, seq, length, action, error, p1, p2)
    struct.pack_into("<H", response, 12, stentura._crc(response, 1, 11))
    if data:
        response[14 : 14 + len(data)] = data
        struct.pack_into("<H", response, 14 + len(data), stentura._crc(data))
    return response


def make_read_response(seq, data=b""):
    return make_response(seq, stentura._READC, p1=len(data), data=data)


def make_readc_packets(data):
    requests, responses = [], []
    seq = stentura._SequenceCounter()
    buf = bytearray(256)
    block, byte = 0, 0
    while data:
        s = seq()
        chunk = data[0:512]
        data = data[512:]
        q = stentura._make_read(buf, s, block, byte)
        requests.append(bytes(q))
        r = make_read_response(s, chunk)
        responses.append(bytes(r))
        byte += len(chunk)
        if byte >= 512:
            block += 1
            byte -= 512
    s = seq()
    q = stentura._make_read(buf, s, block, byte)
    requests.append(bytes(q))
    r = make_read_response(s)
    responses.append(bytes(r))
    return requests, responses


def parse_request(request):
    header = struct.unpack_from("<2B8H", request)
    if header[2] > 18:
        header = list(header) + [request[18:-2], struct.unpack("<H", request[-2:])]
    else:
        header = list(header) + [None] * 2
    return dict(
        zip(
            [
                "SOH",
                "seq",
                "length",
                "action",
                "p1",
                "p2",
                "p3",
                "p4",
                "p5",
                "crc",
                "data",
                "data_crc",
            ],
            header,
        )
    )


class MockPacketPort:
    def __init__(self, responses, requests=None):
        self._responses = responses
        self.writes = 0
        self._requests = requests
        self._current_response_offset = None

    def write(self, data):
        self.writes += 1
        if self._requests and self._requests[self.writes - 1] != bytes(data):
            raise RuntimeError("Wrong packet.")
        self._current_response_offset = 0
        return len(data)

    def read(self, count):
        response = self._responses[self.writes - 1]
        data = response[
            self._current_response_offset : self._current_response_offset + count
        ]
        self._current_response_offset += count
        return data


def test_crc():
    data = bytearray(b"123456789")
    assert stentura._crc(data) == 0xBB3D


def test_write_buffer():
    buf = bytearray()
    data = [1, 2, 3]
    stentura._write_to_buffer(buf, 0, data)
    assert list(buf) == data
    stentura._write_to_buffer(buf, 0, [5, 6])
    assert list(buf) == [5, 6, 3]


def test_parse_stroke():
    # SAT
    a = 0b11001000
    b = 0b11000100
    c = 0b11000000
    d = 0b11001000
    assert sorted(stentura._parse_stroke(a, b, c, d)) == sorted(["S-", "A-", "-T"])


# 11^#STKP 11WHRAO* 11EUFRPB 11LGTSDZ
# PRAOERBGS
def test_parse_strokes():
    data = bytearray()
    # SAT
    a = 0b11001000
    b = 0b11000100
    c = 0b11000000
    d = 0b11001000
    data.extend([a, b, c, d])
    # PRAOERBGS
    a = 0b11000001
    b = 0b11001110
    c = 0b11100101
    d = 0b11010100
    data.extend([a, b, c, d])
    for result, expected in zip(
        stentura._parse_strokes(bytes(data)),
        [["S-", "A-", "-T"], ["P-", "R-", "A-", "O-", "-E", "-R", "-B", "-G", "-S"]],
    ):
        assert sorted(result) == sorted(expected)


def test_make_request():
    buf = bytearray(range(256))
    seq = 2
    action = stentura._OPEN
    p1, p2, p3, p4, p5 = 1, 2, 3, 4, 5
    p = stentura._make_request(buf, action, seq, p1, p2, p3, p4, p5)
    for_crc = [seq, 18, 0, action, 0, p1, 0, p2, 0, p3, 0, p4, 0, p5, 0]
    crc = stentura._crc(for_crc)
    expected = bytearray([1] + for_crc + [crc & 0xFF, crc >> 8])
    assert p == expected
    # Now with data.
    data = b"Testing Testing 123"
    p = stentura._make_request(buf, action, seq, p1, p2, p3, p4, p5, data)
    length = 18 + len(data) + 2
    for_crc = [
        seq,
        length & 0xFF,
        length >> 8,
        action,
        0,
        p1,
        0,
        p2,
        0,
        p3,
        0,
        p4,
        0,
        p5,
        0,
    ]
    crc = stentura._crc(for_crc)
    data_crc = stentura._crc(data)
    expected = bytearray([1] + for_crc + [crc & 0xFF, crc >> 8])
    expected.extend(data)
    expected.extend([data_crc & 0xFF, data_crc >> 8])
    assert p == expected


def test_make_open():
    buf = bytearray(range(32))  # Start with junk in the buffer.
    seq = 79
    drive = b"A"
    filename = b"REALTIME.000"
    p = stentura._make_open(buf, seq, drive, filename)
    for_crc = [
        seq,
        20 + len(filename),
        0,
        stentura._OPEN,
        0,
        ord(drive),
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
    ]
    crc = stentura._crc(for_crc)
    data_crc = stentura._crc(filename)
    expected = bytearray([1] + for_crc + [crc & 0xFF, crc >> 8])
    expected.extend(filename)
    expected.extend([data_crc & 0xFF, data_crc >> 8])
    assert p == expected


def test_make_read():
    buf = bytearray(range(32))  # Start with junk in the buffer.
    seq = 32
    block = 1
    byte = 8
    length = 20
    p = stentura._make_read(buf, seq, block, byte, length)
    for_crc = [seq, 18, 0, stentura._READC, 0, 1, 0, 0, 0, length, 0, block, 0, byte, 0]
    crc = stentura._crc(for_crc)
    expected = bytearray([1] + for_crc + [crc & 0xFF, crc >> 8])
    assert p == expected


def test_make_reset():
    buf = bytearray(range(32))  # Start with junk in the buffer.
    seq = 67
    p = stentura._make_reset(buf, seq)
    for_crc = [seq, 18, 0, stentura._RESET, 0] + ([0] * 10)
    crc = stentura._crc(for_crc)
    expected = bytearray([1] + for_crc + [crc & 0xFF, crc >> 8])
    assert p == expected


VALIDATE_RESPONSE_TESTS = (
    ("valid, no data", make_response(5, 9, 1, 2, 3), True),
    ("valid, data", make_response(5, 9, 1, 2, 3, data=b"hello"), True),
    ("short", make_response(5, 9, 1, 2, 3)[:12], False),
    ("length long", make_response(5, 9, 1, 2, 3, length=15), False),
    ("length short", make_response(5, 9, 1, 2, 3, data=b"foo", length=15), False),
    ("bad data", make_response(5, 9, 1, 2, 3) + b"1", False),
    ("bad crc", make_response(5, 9, 1, 2, 3)[:-1] + b"1", False),
    ("bad data crc", make_response(5, 9, 1, 2, 3, data=b"foo")[:-1] + b"1", False),
)


@pytest.mark.parametrize(
    "packet, valid",
    [t[1:] for t in VALIDATE_RESPONSE_TESTS],
    ids=[t[0] for t in VALIDATE_RESPONSE_TESTS],
)
def test_validate_response(packet, valid):
    assert stentura._validate_response(packet) == valid


def test_read_data_simple():
    class MockPort:
        def read(self, count):
            if count != 5:
                raise RuntimeError("Incorrect number read.")
            return b"12345"

    port = MockPort()
    buf = bytearray([0] * 20)
    count = stentura._read_data(port, threading.Event(), buf, 0, 5)
    assert count == 5
    assert buf == b"12345" + (b"\x00" * 15)

    # Test the offset parameter.
    count = stentura._read_data(port, threading.Event(), buf, 4, 5)
    assert buf == b"123412345" + (b"\x00" * 11)


def test_read_data_stop_set():
    class MockPort:
        def read(self, count):
            return b"0000"

    buf = bytearray()
    event = threading.Event()
    event.set()
    with pytest.raises(stentura._StopException):
        stentura._read_data(MockPort(), event, buf, 0, 4)


def test_read_data_timeout():
    class MockPort:
        def read(self, count):
            # When serial time out occurs read() returns
            # less characters as requested
            return "123"

    port = MockPort()
    buf = bytearray()
    with pytest.raises(stentura._TimeoutException):
        stentura._read_data(port, threading.Event(), buf, 0, 4)


def test_read_packet_simple():
    class MockPort:
        def __init__(self, packet):
            self._packet = packet

        def read(self, count):
            requested_bytes = self._packet[0:count]
            self._packet = self._packet[count:]
            return requested_bytes

    buf = bytearray(256)
    for packet in [
        make_response(1, 2, 3, 4, 5),
        make_response(1, 2, 3, 4, 5, b"hello"),
    ]:
        port = MockPort(packet)
        response = stentura._read_packet(port, threading.Event(), buf)
        assert response == packet


def test_read_packet_fail():
    class MockPort:
        def __init__(
            self,
            data_section_length=0,
            set1=False,
            set2=False,
            give_too_much_data=False,
            give_timeout=False,
        ):
            self._set1 = set1
            self._set2 = set2
            self._read1 = False
            self._read2 = False
            self.event = threading.Event()
            self._give_timeout = give_timeout
            self._data = [1, 0, data_section_length + 4, 0] + [0] * data_section_length
            if give_too_much_data:
                self._data.append(0)
            self._data = bytearray(self._data)

        def read(self, count):
            if not self._read1:
                self._read1 = True
                if self._set1:
                    self.event.set()
            elif not self._read2:
                self._read2 = True
                if self._set2:
                    self.event.set()
            else:
                raise RuntimeError("Already read data.")
            if self._give_timeout and len(self._data) == count:
                # If read() returns less bytes what was requested,
                # it indicates a timeout.
                count -= 1
            requested_bytes = self._data[0:count]
            self._data = self._data[count:]
            return requested_bytes

    buf = bytearray()

    with pytest.raises(stentura._StopException):
        port = MockPort(set1=True)
        stentura._read_packet(port, port.event, buf)

    with pytest.raises(stentura._StopException):
        port = MockPort(data_section_length=30, set2=True)
        stentura._read_packet(port, port.event, buf)

    with pytest.raises(stentura._TimeoutException):
        port = MockPort(give_timeout=True)
        stentura._read_packet(port, port.event, buf)

    with pytest.raises(stentura._TimeoutException):
        port = MockPort(data_section_length=30, give_timeout=True)
        stentura._read_packet(port, port.event, buf)

    with pytest.raises(stentura._ProtocolViolationException):
        port = MockPort(give_too_much_data=True)
        stentura._read_packet(port, port.event, buf)


def test_write_to_port():
    class MockPort:
        def __init__(self, chunk):
            self._chunk = chunk
            self.data = b""

        def write(self, data):
            data = data[: self._chunk]
            self.data += data
            return len(data)

    data = bytearray(range(20))

    # All in one shot.
    port = MockPort(20)
    stentura._write_to_port(port, data)
    assert data == port.data

    # In parts.
    port = MockPort(5)
    stentura._write_to_port(port, data)
    assert data == port.data


def test_send_receive():
    event = threading.Event()
    buf, seq, action = bytearray(256), 5, stentura._OPEN
    request = stentura._make_request(bytearray(256), stentura._OPEN, seq)
    correct_response = make_response(seq, action)
    wrong_seq = make_response(seq - 1, action)
    wrong_action = make_response(seq, action + 1)
    bad_response = make_response(seq, action, data=b"foo", length=15)

    # Correct response first time.
    responses = [correct_response]
    port = MockPacketPort(responses)
    response = stentura._send_receive(port, event, request, buf)
    assert response == correct_response

    # Timeout once then correct response.
    responses = [b"", correct_response]
    port = MockPacketPort(responses)
    response = stentura._send_receive(port, event, request, buf)
    assert response == correct_response

    # Wrong sequence number then correct response.
    responses = [wrong_seq, correct_response]
    port = MockPacketPort(responses)
    response = stentura._send_receive(port, event, request, buf)
    assert response == correct_response

    # No correct responses. Also make sure max_retries is honored.
    max_tries = 6
    responses = [b""] * max_tries
    port = MockPacketPort(responses)
    with pytest.raises(stentura._ConnectionLostException):
        stentura._send_receive(port, event, request, buf, max_tries)
    assert max_tries == port.writes

    # Wrong action.
    responses = [wrong_action]
    port = MockPacketPort(responses)
    with pytest.raises(stentura._ProtocolViolationException):
        stentura._send_receive(port, event, request, buf)

    # Bad packet.
    responses = [bad_response]
    port = MockPacketPort(responses)
    with pytest.raises(stentura._ProtocolViolationException):
        stentura._send_receive(port, event, request, buf)

    # Stopped.
    responses = [""]
    event.set()
    port = MockPacketPort(responses)
    with pytest.raises(stentura._StopException):
        stentura._send_receive(port, event, request, buf)


def test_sequence_counter():
    seq = stentura._SequenceCounter()
    actual = [seq() for x in range(512)]
    expected = list(range(256)) * 2
    assert actual == expected

    seq = stentura._SequenceCounter(67)
    actual = [seq() for x in range(512)]
    expected = list(range(67, 256)) + list(range(256)) + list(range(67))
    assert actual == expected


def test_read():
    request_buf = bytearray(256)
    response_buf = bytearray(256)
    stroke_buf = bytearray(256)
    event = threading.Event()

    tests = ([0b11000001] * (3 * 512 + 28), [0b11010101] * 4, [0b11000010] * 8)

    for data in tests:
        data = bytearray(data)
        requests, responses = make_readc_packets(data)
        port = MockPacketPort(responses, requests)
        seq = stentura._SequenceCounter()
        block, byte = 0, 0
        block, byte, response = stentura._read(
            port, event, seq, request_buf, response_buf, stroke_buf, block, byte
        )
        assert data == bytes(response)
        assert block == len(data) // 512
        assert byte == len(data) % 512


def test_loop():
    class Event:
        def __init__(self, count, data, stop=False):
            self.count = count
            self.data = data
            self.stop = stop

        def __repr__(self):
            return f"<{self.count}, {self.data}, {self.stop}>"

    class MockPort:
        def __init__(self, events=()):
            self._file = b""
            self._out = b""
            self._is_open = False
            self.event = threading.Event()
            self.count = 0
            self.events = [Event(*x) for x in sorted(events, key=lambda x: x[0])]

        def write(self, request):
            # Process the packet and put together a response.
            p = parse_request(request)
            if p["action"] == stentura._OPEN:
                self._out = make_response(p["seq"], p["action"])
                self._is_open = True
            elif p["action"] == stentura._READC:
                if not self._is_open:
                    raise RuntimeError("no open")
                length, block, byte = p["p3"], p["p4"], p["p5"]
                seq = p["seq"]
                action = stentura._READC
                start = block * 512 + byte
                end = start + length
                data = self._file[start:end]
                self._out = make_response(seq, action, p1=len(data), data=data)
            while self.events and self.events[0].count <= self.count:
                event = self.events.pop(0)
                self.append(event.data)
                if event.stop:
                    self.event.set()
            self.count += 1
            return len(request)

        def read(self, count):
            requested_bytes = self._out[0:count]
            self._out = self._out[count:]
            return requested_bytes

        def append(self, data):
            self._file += data
            return self

        def flushInput(self):
            pass

        def flushOutput(self):
            pass

    data1 = bytearray([0b11001010] * 4 * 9)
    data1_trans = [["S-", "K-", "R-", "O-", "-F", "-P", "-T", "-D"]] * 9
    data2 = bytearray([0b11001011] * 4 * 30)

    tests = [
        # No inputs but nothing crashes either.
        (MockPort([(30, b"", True)]), []),
        # A few strokes.
        (MockPort([(23, data1), (43, b"", True)]), data1_trans),
        # Ignore data that's there before we started.
        (MockPort([(46, b"", True)]).append(data2), []),
        # Ignore data that was there and also parse some strokes.
        (MockPort([(25, data1), (36, b"", True)]).append(data2), data1_trans),
    ]

    for test in tests:
        read_data = []

        def callback(data, read_data=read_data):
            read_data.append(data)

        port = test[0]
        expected = test[1]

        ready_called = [False]

        def ready(ready_called=ready_called):
            ready_called[0] = True

        try:
            ready_called[0] = False
            stentura._loop(port, port.event, callback, ready, timeout=0)
        except stentura._StopException:
            pass
        assert read_data == expected
        assert ready_called[0]


# TODO: add a test on the machine itself with mocks
