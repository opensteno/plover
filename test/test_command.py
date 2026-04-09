"""Unit tests for built-in engine command plugins."""

import ast

import pytest

from plover.formatting import SPACE_PLACEMENT_AFTER

from plover.command.set_config import set_config
from plover.config import Config, DictionaryConfig

from plover_build_utils.testing import parametrize

from .test_config import DEFAULTS, DEFAULT_KEYMAP


class FakeEngine:
    """The plugin sets the engine.config property, which unpacks a dict as
    keywords into config.update."""

    def __init__(self):
        self._cfg = Config()

    @property
    def config(self):
        return self._cfg.as_dict()

    @config.setter
    def config(self, options):
        self._cfg.update(**options)


SET_CONFIG_TESTS = (
    lambda: (
        '"space_placement":"{SPACE_PLACEMENT_AFTER}"'.format(
            SPACE_PLACEMENT_AFTER=SPACE_PLACEMENT_AFTER
        ),
        SPACE_PLACEMENT_AFTER,
    ),
    lambda: ('"start_attached":True', True),
    lambda: ('"undo_levels":10', 10),
    lambda: (
        '"log_file_name":"c:/whatever/morestrokes.log"',
        "c:/whatever/morestrokes.log",
    ),
    lambda: ('"enabled_extensions":[]', set()),
    lambda: ('"machine_type":"Keyboard"', "Keyboard"),
    lambda: (
        '"machine_specific_options":{"arpeggiate":True}',
        {"arpeggiate": True, "first_up_chord_send": False},
    ),
    lambda: ('"system_keymap":' + str(DEFAULT_KEYMAP), DEFAULT_KEYMAP),
    lambda: (
        '"dictionaries":("user.json","main.json")',
        list(map(DictionaryConfig, ("user.json", "main.json"))),
    ),
)


@parametrize(SET_CONFIG_TESTS)
def test_set_config(cmdline, expected):
    """Unit tests for set_config command. Test at least one of each valid data type."""
    # Config values are sometimes converted and stored as different types than the input,
    # so the expected output config values may not always be strictly equal to the input.
    engine = FakeEngine()
    engine.config = DEFAULTS
    set_config(engine, cmdline)
    key = ast.literal_eval("{" + cmdline + "}").popitem()[0]
    assert engine.config[key] == expected


def test_set_config_multiple_options():
    """Multiple options can be set with one command if separated by commas.
    Try setting every test option from scratch with a single command."""
    engine = FakeEngine()
    engine.config = DEFAULTS
    individual_tests = [t() for t in SET_CONFIG_TESTS]
    compound_cmdline = ",".join([t[0] for t in individual_tests])
    set_config(engine, compound_cmdline)
    for cmdline, expected in individual_tests:
        key = ast.literal_eval("{" + cmdline + "}").popitem()[0]
        assert engine.config[key] == expected


SET_CONFIG_INVALID_TESTS = (
    # No delimiter in command.
    lambda: '"undo_levels"10',
    # Wrong value type.
    lambda: '"undo_levels":"does a string work?"',
    # Unsupported value.
    lambda: '"machine_type":"Telepathy"',
    # Bad format for dict literal.
    lambda: '"machine_specific_options":{"closing_brace":False',
)


@parametrize(SET_CONFIG_INVALID_TESTS, arity=1)
def test_set_config_invalid(invalid_cmdline):
    """Unit tests for set_config exception handling."""
    engine = FakeEngine()
    with pytest.raises(ValueError):
        set_config(engine, invalid_cmdline)
