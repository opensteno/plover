# Copyright (c) 2013 Hesky Fisher
# See LICENSE.txt for details.

import os
from collections import defaultdict
from logging import Handler
from typing import ClassVar

import pytest

from plover import log
from plover.steno import Stroke


class FakeHandler(Handler):
    outputs: ClassVar[defaultdict] = defaultdict(list)

    def __init__(self, filename, format=log.STROKE_LOG_FORMAT):
        super().__init__()
        self.baseFilename = filename

    def emit(self, record):
        FakeHandler.outputs[self.baseFilename].append(record.getMessage())


@pytest.fixture(autouse=True)
def fake_file_log(monkeypatch):
    monkeypatch.setattr("plover.log.FileHandler", FakeHandler)
    yield
    FakeHandler.outputs.clear()
    # Reset logger state.
    log.set_stroke_filename(None)
    log.enable_stroke_logging(False)
    log.enable_translation_logging(False)


def stroke_filename(path):
    return os.path.abspath(path)


def test_set_filename():
    sf1 = stroke_filename("/fn1")
    log.set_stroke_filename("/fn1")
    log.enable_stroke_logging(True)
    log.stroke(Stroke(("S-",)))
    sf2 = stroke_filename("/fn2")
    log.set_stroke_filename("/fn2")
    log.stroke(Stroke(("-T",)))
    log.set_stroke_filename(None)
    log.stroke(Stroke(("P-",)))
    assert FakeHandler.outputs == {
        sf1: ["Stroke(S : ['S-'])"],
        sf2: ["Stroke(-T : ['-T'])"],
    }


def test_stroke():
    sf = stroke_filename("/fn")
    log.set_stroke_filename(sf)
    log.enable_stroke_logging(True)
    log.stroke(Stroke(("S-", "-T", "T-")))
    log.stroke(Stroke(("#", "S-", "-T")))
    assert FakeHandler.outputs == {
        sf: ["Stroke(ST-T : ['S-', 'T-', '-T'])", "Stroke(1-9 : ['#', 'S-', '-T'])"],
    }


def test_log_translation():
    sf = stroke_filename("/fn")
    log.set_stroke_filename(sf)
    log.enable_translation_logging(True)
    log.translation(["a", "b"], ["c", "d"], None)
    assert FakeHandler.outputs == {sf: ["*a", "*b", "c", "d"]}


def test_enable_stroke_logging():
    sf = stroke_filename("/fn")
    log.set_stroke_filename(sf)
    log.stroke(Stroke(("S-",)))
    log.enable_stroke_logging(True)
    log.stroke(Stroke(("T-",)))
    log.enable_stroke_logging(False)
    log.stroke(Stroke(("K-",)))
    assert FakeHandler.outputs == {sf: ["Stroke(T : ['T-'])"]}


def test_enable_translation_logging():
    sf = stroke_filename("/fn")
    log.set_stroke_filename(sf)
    log.translation(["a"], ["b"], None)
    log.enable_translation_logging(True)
    log.translation(["c"], ["d"], None)
    log.enable_translation_logging(False)
    log.translation(["e"], ["f"], None)
    assert FakeHandler.outputs == {sf: ["*c", "d"]}
