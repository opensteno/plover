# Copyright (c) 2013 Hesky Fisher
# See LICENSE.txt for details.

"""Unit tests for steno.py."""

import inspect

import pytest

from plover.steno import Stroke, normalize_steno
from plover_build_utils.testing import parametrize

NORMALIZE_TESTS = (
    lambda: ("S", ("S",)),
    lambda: ("S-", ("S",)),
    lambda: ("-S", ("-S",)),
    lambda: ("ES", ("ES",)),
    lambda: ("-ES", ("ES",)),
    lambda: ("TW-EPBL", ("TWEPBL",)),
    lambda: ("TWEPBL", ("TWEPBL",)),
    lambda: ("RR", ("R-R",)),
    lambda: ("19", ("1-9",)),
    lambda: ("14", ("14",)),
    lambda: ("146", ("14-6",)),
    lambda: ("67", ("-67",)),
    lambda: ("120-7", ("1207",)),
    lambda: ("6", ("-6",)),
    lambda: ("9", ("-9",)),
    lambda: ("5", ("5",)),
    lambda: ("0", ("0",)),
    lambda: ("456", ("456",)),
    lambda: ("46", ("4-6",)),
    lambda: ("4*6", ("4*6",)),
    lambda: ("456", ("456",)),
    lambda: ("S46", ("14-6",)),
    lambda: ("T-EFT/-G", ("TEFT", "-G")),
    lambda: ("T-EFT/G", ("TEFT", "-G")),
    lambda: ("/PRE", ("", "PRE")),
    lambda: ("S--T", ("S-T",)),
    # Number key.
    lambda: ("#", ("#",)),
    lambda: ("#S", ("1",)),
    lambda: ("#A", ("5",)),
    lambda: ("#0", ("0",)),
    lambda: ("#6", ("-6",)),
    # RTF/CRE spec allow the number key letter anywhere…
    lambda: ("#WS", ("#W-S",)),
    lambda: ("W#S", ("#W-S",)),
    lambda: ("W-S#", ("#W-S",)),
    lambda: ("S#A", ("15",)),
    lambda: ("2#", ("2",)),
    # Implicit hyphens.
    lambda: ("SA-", ("SA",)),
    lambda: ("SA-R", ("SAR",)),
    lambda: ("O", ("O",)),
    lambda: ("O-", ("O",)),
    lambda: ("S*-R", ("S*R",)),
    # Invalid.
    lambda: ("SRALD/invalid", (ValueError, ("SRALD", "invalid"))),
    lambda: ("SRALD//invalid", (ValueError, ("SRALD", "", "invalid"))),
    lambda: ("S-*R", (ValueError, ("S-*R",))),
    lambda: ("-O-", (ValueError, ("-O-",))),
    lambda: ("-O", (ValueError, ("-O",))),
    lambda: ("#WS#", (ValueError, ("#WS#",))),
)


@parametrize(NORMALIZE_TESTS)
@pytest.mark.parametrize("mode", ("strict=False", "strict=True"))
def test_normalize_steno(mode, steno, expected):
    kwargs = eval("dict(" + mode + ")")
    if inspect.isclass(expected[0]):
        if kwargs["strict"]:
            with pytest.raises(expected[0]):
                normalize_steno(steno)
            return
        expected = expected[1]
    result = normalize_steno(steno, **kwargs)
    msg = f"normalize_steno({steno!r}, {mode})={result!r} != {expected!r}"
    assert result == expected, msg


STROKE_TESTS = (
    lambda: (["S-"], (["S-"], "S")),
    lambda: (["S-", "T-"], (["S-", "T-"], "ST")),
    lambda: (["T-", "S-"], (["S-", "T-"], "ST")),
    lambda: (["-P", "-P"], (["-P"], "-P")),
    lambda: (["#", "S-", "-T"], (["#", "S-", "-T"], "1-9")),
    lambda: (["1-", "-9"], (["#", "S-", "-T"], "1-9")),
    lambda: (["-P", "X-"], ValueError),
)


@parametrize(STROKE_TESTS)
def test_stroke(keys, expected):
    if inspect.isclass(expected):
        with pytest.raises(expected):
            Stroke(keys)
    else:
        steno_keys, rtfcre = expected
        stroke = Stroke(keys)
        assert stroke.steno_keys == steno_keys
        assert stroke.rtfcre == rtfcre
