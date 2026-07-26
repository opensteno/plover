# Copyright (c) 2011 Hesky Fisher
# See LICENSE.txt for details.

"""Unit tests for passport.py."""

import threading
from typing import ClassVar

from plover.machine.passport import Passport
from plover_build_utils.testing import parametrize


class MockSerial:
    def __init__(self, **params):
        pass

    def isOpen(self):
        return True

    def inWaiting(self):
        return len(self.data)

    def read(self, size=1):
        assert size >= self.inWaiting()
        if not self.data:
            return ""
        data = self.data.pop(0)
        if not self.data:
            self.event.set()
        return data

    def close(self):
        pass


PASSPORT_TESTS = (
    # Test all keys
    lambda: (
        (b"!f#f+f*fAfCfBfEfDfGfFfHfKfLfOfNfQfPfSfRfUfTfWfYfXfZf^f~f",),
        [
            set(Passport.get_keys()),
        ],
    ),
    # Anything below 8 is not registered
    lambda: (
        (b"S9T8A7",),
        [
            ["S", "T"],
        ],
    ),
    # Sequence of strokes
    lambda: (
        (b"SfTf", b"Zf", b"QfLf"),
        [
            ["S", "T"],
            [
                "Z",
            ],
            ["Q", "L"],
        ],
    ),
)


@parametrize(PASSPORT_TESTS)
def test_passport(monkeypatch, inputs, expected):
    params = {k: v[0] for k, v in Passport.get_option_info().items()}

    class mock(MockSerial):
        event = threading.Event()
        data: ClassVar[list] = [b"<123/" + s + b"/something>" for s in inputs]

    monkeypatch.setattr("plover.machine.base.serial.Serial", mock)
    actual = []
    m = Passport(params)
    m.add_stroke_callback(actual.append)
    m.start_capture()
    mock.event.wait()
    m.stop_capture()
    assert len(actual) == len(expected)
    for actual_keys, expected_keys in zip(actual, expected):
        assert sorted(actual_keys) == sorted(expected_keys)
