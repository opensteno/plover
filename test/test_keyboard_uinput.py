from unittest import mock

import pytest

uinput = pytest.importorskip("plover.oslayer.linux.keyboardcontrol_uinput")

DELAY_MS = 100


@pytest.fixture
def emulation():
    """Keyboard emulation that records the key events and the delays in order."""
    events = []
    with (
        mock.patch.object(uinput, "UInput") as ui,
        mock.patch.object(uinput, "process_iter", return_value=[]),
        mock.patch("plover.output.keyboard.sleep") as sleep,
    ):
        ui.return_value.write.side_effect = lambda _type, code, value: events.append(
            (code, value)
        )
        sleep.side_effect = lambda _seconds: events.append("sleep")
        emulation = uinput.KeyboardEmulation()
        emulation._key_to_keycodeinfo = uinput.LAYOUTS[uinput.DEFAULT_LAYOUT]
        emulation.set_key_press_delay(DELAY_MS)
        yield emulation, events


def test_characters_without_modifiers_get_one_delay_each(emulation):
    emu, events = emulation
    assert not emu._get_key("a")[1]

    emu.send_string("ab")

    assert events.count("sleep") == 2


def test_backspaces_get_one_delay_each(emulation):
    emu, events = emulation
    assert emu._get_key("\b")[0] is not None

    emu.send_backspaces(3)

    assert events.count("sleep") == 3


def test_shifted_character_keeps_a_delay_between_modifier_and_key(emulation):
    emu, events = emulation
    base, mods = emu._get_key("A")
    assert mods

    emu.send_string("A")

    before_key = events[: events.index((base, 1))]
    assert [(mod, 1) for mod in mods] == [ev for ev in before_key if ev != "sleep"]
    assert "sleep" in before_key
    assert events.count("sleep") == 2
