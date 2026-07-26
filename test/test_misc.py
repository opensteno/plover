# Copyright (c) 2016 Open Steno Project
# See LICENSE.txt for details.

"""Tests for misc.py."""

import inspect
import os

import pytest

import plover.oslayer.config as conf
from plover import misc
from plover.resource import ASSET_SCHEME
from plover_build_utils.testing import parametrize


def test_popcount_8():
    for n in range(256):
        assert misc.popcount_8(n) == format(n, "b").count("1")
    with pytest.raises(AssertionError):
        misc.popcount_8(256)
    with pytest.raises(AssertionError):
        misc.popcount_8(-1)


if conf.PLATFORM == "win":
    ABS_PATH = os.path.normcase(r"c:\foo\bar")
else:
    ABS_PATH = "/foo/bar"


@parametrize(
    (
        # Asset, no change.
        lambda: (ASSET_SCHEME + "foo:bar", ASSET_SCHEME + "foo:bar"),
        # Absolute path, no change.
        lambda: (ABS_PATH, ABS_PATH),
        # Relative path, resolve relative to configuration directory.
        lambda: (
            os.path.normcase(os.path.normpath("foo/bar")),
            os.path.normcase(
                os.path.join(os.path.realpath(conf.CONFIG_DIR), "foo", "bar")
            ),
        ),
        # Path below the user home directory.
        lambda: (
            os.path.normcase(os.path.normpath("~/foo/bar")),
            os.path.normcase(os.path.expanduser(os.path.normpath("~/foo/bar"))),
        ),
    )
)
def test_dictionary_path(short_path, full_path):
    for input, function, expected in (
        # Unchanged.
        (short_path, "shorten", short_path),
        (full_path, "expand", full_path),
        # Shorten.
        (full_path, "shorten", short_path),
        # Expand.
        (short_path, "expand", full_path),
    ):
        function = f"{function}_path"
        result = getattr(misc, function)(input)
        assert result == expected, function


@parametrize(
    (
        # Boolean.
        lambda: (False, False),
        lambda: (True, True),
        # True string values.
        lambda: ("1", True),
        lambda: ("yes", True),
        lambda: ("true", True),
        lambda: ("on", True),
        # False string values.
        lambda: ("0", False),
        lambda: ("no", False),
        lambda: ("false", False),
        lambda: ("off", False),
        # Invalid string values.
        lambda: ("yep", ValueError),
        lambda: ("nope", ValueError),
        # Other types.
        lambda: (0, False),
        lambda: (1, True),
        lambda: (42, True),
        lambda: (4.2, True),
        lambda: (0.0, False),
        lambda: (None, False),
    )
)
def test_boolean(input, output):
    if inspect.isclass(output):
        with pytest.raises(output):
            misc.boolean(input)
    else:
        assert misc.boolean(input) == output


def test_to_surrogate_pairs():
    # Split unicode characters above 0xFFFF
    assert misc.to_surrogate_pair(chr(0x1F4A6)) == [0xD83D, 0xDCA6]
    # Do not slit characters below 0xFFFF
    assert misc.to_surrogate_pair(chr(0x20)) == [0x20]
    # Do not split already split characters.
    assert misc.to_surrogate_pair(chr(0xD83D) + chr(0xDCA6)) == [0xD83D, 0xDCA6]
