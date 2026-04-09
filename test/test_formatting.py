# Copyright (c) 2013 Hesky Fisher
# See LICENSE.txt for details.

"""Unit tests for formatting.py."""

import inspect

import pytest

from plover import formatting
from plover.formatting import (
    Case,
    SPACE_PLACEMENT_AFTER,
)

from plover_build_utils.testing import CaptureOutput, parametrize


def action(**kwargs):
    # Support using something like `text_and_word='stuff'`
    # as a shortcut for `text='stuff', word='stuff'`.
    for k, v in list(kwargs.items()):
        if "_and_" in k:
            del kwargs[k]
            for k in k.split("_and_"):
                kwargs[k] = v
    return formatting._Action(**kwargs)


class MockTranslation:
    def __init__(self, rtfcre=tuple(), english=None, formatting=None):
        self.rtfcre = rtfcre
        self.english = english
        self.formatting = formatting

    def __str__(self):
        return str(self.__dict__)


def translation(**kwargs):
    return MockTranslation(**kwargs)


STARTING_STROKE_TESTS = (
    lambda: (
        True,
        True,
        [],
        [translation(rtfcre=("S"), english="hello")],
        None,
        ([action(prev_attach=True, text="Hello", trailing_space=" ", word="hello")],),
        [("s", "Hello")],
    ),
    lambda: (
        False,
        False,
        [],
        [translation(rtfcre=("S"), english="hello")],
        None,
        ([action(text_and_word="hello", trailing_space=" ")],),
        [("s", " hello")],
    ),
    lambda: (
        True,
        False,
        [],
        [translation(rtfcre=("S"), english="hello")],
        None,
        ([action(text="Hello", word="hello", trailing_space=" ")],),
        [("s", " Hello")],
    ),
    lambda: (
        False,
        True,
        [],
        [translation(rtfcre=("S"), english="hello")],
        None,
        ([action(text_and_word="hello", prev_attach=True, trailing_space=" ")],),
        [("s", "hello")],
    ),
)


@parametrize(STARTING_STROKE_TESTS)
def test_starting_stroke(
    capitalized, attached, undo, do, prev, expected_formats, expected_outputs
):
    output = CaptureOutput()
    formatter = formatting.Formatter()
    formatter.set_output(output)
    formatter.start_capitalized = capitalized
    formatter.start_attached = attached
    formatter.format(undo, do, prev)
    for i, t in enumerate(do):
        assert t.formatting == expected_formats[i]
    assert output.instructions == expected_outputs


FORMATTER_TESTS = (
    lambda: (
        [translation(formatting=[action(text_and_word="hello", trailing_space=" ")])],
        [],
        None,
        (),
        [("b", 6)],
    ),
    lambda: (
        [],
        [translation(rtfcre=("S"), english="hello")],
        [
            translation(
                rtfcre=("T"),
                english="a",
                formatting=[action(text_and_word="f", trailing_space=" ")],
            )
        ],
        ([action(text_and_word="hello", trailing_space=" ")],),
        [("s", " hello")],
    ),
    lambda: (
        [],
        [translation(rtfcre=("S"), english="hello")],
        None,
        ([action(text_and_word="hello", trailing_space=" ")],),
        [("s", " hello")],
    ),
    lambda: (
        [],
        [translation(rtfcre=("ST-T",))],
        None,
        ([action(text_and_word="ST-T", trailing_space=" ")],),
        [("s", " ST-T")],
    ),
    lambda: (
        [],
        [translation(rtfcre=("ST-T",))],
        [translation(formatting=[action(text_and_word="hi", trailing_space=" ")])],
        ([action(text_and_word="ST-T", trailing_space=" ")],),
        [("s", " ST-T")],
    ),
    lambda: (
        [translation(formatting=[action(text_and_word="test", trailing_space=" ")])],
        [translation(english="rest")],
        [
            translation(
                formatting=[action(next_case=Case.CAP_FIRST_WORD, trailing_space=" ")]
            )
        ],
        ([action(text="Rest", word="rest", trailing_space=" ")],),
        [("b", 4), ("s", "Rest")],
    ),
    lambda: (
        [
            translation(
                formatting=[
                    action(text_and_word="dare"),
                    action(
                        prev_attach=True, text="ing", word="daring", prev_replace="e"
                    ),
                ]
            )
        ],
        [translation(english="rest")],
        [
            translation(
                formatting=[action(next_case=Case.CAP_FIRST_WORD, trailing_space=" ")]
            )
        ],
        ([action(text="Rest", word="rest", trailing_space=" ")],),
        [("b", 6), ("s", "Rest")],
    ),
    lambda: (
        [translation(formatting=[action(text_and_word="drive", trailing_space=" ")])],
        [translation(english="driving")],
        None,
        ([action(text_and_word="driving", trailing_space=" ")],),
        [("b", 1), ("s", "ing")],
    ),
    lambda: (
        [translation(formatting=[action(text_and_word="drive", trailing_space=" ")])],
        [translation(english="{#c}driving")],
        None,
        ([action(combo="c"), action(text_and_word="driving", trailing_space=" ")],),
        [("b", 6), ("c", "c"), ("s", " driving")],
    ),
    lambda: (
        [translation(formatting=[action(text_and_word="drive", trailing_space=" ")])],
        [translation(english="{PLOVER:c}driving")],
        None,
        ([action(command="c"), action(text_and_word="driving", trailing_space=" ")],),
        [("b", 6), ("e", "c"), ("s", " driving")],
    ),
    lambda: (
        [],
        [translation(english="{PloveR:CMD}")],
        None,
        ([action(command="CMD")],),
        [("e", "CMD")],
    ),
    lambda: (
        [],
        [translation(english="{:coMManD:Cmd}")],
        None,
        ([action(command="Cmd")],),
        [("e", "Cmd")],
    ),
    lambda: (
        [],
        [translation(rtfcre=("1",))],
        None,
        ([action(text_and_word="1", trailing_space=" ", glue=True)],),
        [("s", " 1")],
    ),
    lambda: (
        [],
        [translation(rtfcre=("1",))],
        [translation(formatting=[action(text_and_word="hi", trailing_space=" ")])],
        ([action(text_and_word="1", trailing_space=" ", glue=True)],),
        [("s", " 1")],
    ),
    lambda: (
        [],
        [translation(rtfcre=("1",))],
        [
            translation(
                formatting=[action(text_and_word="hi", trailing_space=" ", glue=True)]
            )
        ],
        (
            [
                action(
                    prev_attach=True,
                    text="1",
                    trailing_space=" ",
                    word="hi1",
                    glue=True,
                )
            ],
        ),
        [("s", "1")],
    ),
    lambda: (
        [],
        [translation(rtfcre=("1-9",))],
        [
            translation(
                formatting=[action(text_and_word="hi", trailing_space=" ", glue=True)]
            )
        ],
        (
            [
                action(
                    prev_attach=True,
                    text="19",
                    trailing_space=" ",
                    word="hi19",
                    glue=True,
                )
            ],
        ),
        [("s", "19")],
    ),
    lambda: (
        [],
        [translation(rtfcre=("ST-PL",))],
        [translation(formatting=[action(text_and_word="hi", trailing_space=" ")])],
        ([action(text_and_word="ST-PL", trailing_space=" ")],),
        [("s", " ST-PL")],
    ),
    lambda: (
        [],
        [translation(rtfcre=("ST-PL",))],
        None,
        ([action(text_and_word="ST-PL", trailing_space=" ")],),
        [("s", " ST-PL")],
    ),
)


@parametrize(FORMATTER_TESTS)
def test_formatter(undo, do, prev, expected_formats, expected_outputs):
    output = CaptureOutput()
    # Add some initial blank text so
    # undoing with no previous state
    # does not assert.
    output.text = " " * 128
    formatter = formatting.Formatter()
    formatter.set_output(output)
    formatter.format(undo, do, prev)
    for i, t in enumerate(do):
        assert t.formatting == expected_formats[i]
    assert output.instructions == expected_outputs


def test_action():
    assert action(word="test") != action(word="test", next_attach=True)
    assert action(text="test") == action(text="test")
    assert action(text="test", word="test").copy_state() == action(word="test")


TRANSLATION_TO_ACTIONS_TESTS = (
    lambda: ("test", action(), [action(text_and_word="test", trailing_space=" ")]),
    lambda: (
        "{^^}",
        action(),
        [
            action(
                prev_attach=True, text_and_word="", next_attach=True, orthography=False
            )
        ],
    ),
    lambda: ("1-9", action(), [action(text_and_word="1-9", trailing_space=" ")]),
    lambda: (
        "32",
        action(),
        [action(text_and_word="32", trailing_space=" ", glue=True)],
    ),
    lambda: (
        "",
        action(text_and_word="test", next_attach=True),
        [action(prev_attach=True, word="test", next_attach=True)],
    ),
    lambda: (
        "  ",
        action(text_and_word="test", next_attach=True),
        [action(prev_attach=True, word="test", next_attach=True)],
    ),
    lambda: (
        "{^} {.} hello {.} {#ALT_L(Grave)}{^ ^}",
        action(),
        [
            action(
                prev_attach=True, text_and_word="", next_attach=True, orthography=False
            ),
            action(
                prev_attach=True,
                text_and_word=".",
                trailing_space=" ",
                next_case=Case.CAP_FIRST_WORD,
            ),
            action(text="Hello", word="hello", trailing_space=" "),
            action(
                prev_attach=True,
                text_and_word=".",
                trailing_space=" ",
                next_case=Case.CAP_FIRST_WORD,
            ),
            action(
                word=".",
                trailing_space=" ",
                combo="ALT_L(Grave)",
                next_case=Case.CAP_FIRST_WORD,
            ),
            action(prev_attach=True, text=" ", word="", next_attach=True),
        ],
    ),
    lambda: (
        "{-|}{>}{&a}{>}{&b}",
        action(),
        [
            action(next_case=Case.CAP_FIRST_WORD),
            action(next_case=Case.LOWER_FIRST_CHAR),
            action(text_and_word="a", trailing_space=" ", glue=True),
            action(
                next_case=Case.LOWER_FIRST_CHAR, word="a", trailing_space=" ", glue=True
            ),
            action(
                prev_attach=True, text="b", word="ab", trailing_space=" ", glue=True
            ),
        ],
    ),
    lambda: (
        "{-|}{>}{&a}{>}{&b}",
        action(),
        [
            action(next_case=Case.CAP_FIRST_WORD),
            action(next_case=Case.LOWER_FIRST_CHAR),
            action(text_and_word="a", trailing_space=" ", glue=True),
            action(
                next_case=Case.LOWER_FIRST_CHAR, word="a", trailing_space=" ", glue=True
            ),
            action(
                prev_attach=True, text="b", word="ab", trailing_space=" ", glue=True
            ),
        ],
    ),
    lambda: (
        "{-|} equip {^s}",
        action(),
        [
            action(next_case=Case.CAP_FIRST_WORD),
            action(text="Equip", word="equip", trailing_space=" "),
            action(prev_attach=True, text="s", trailing_space=" ", word="equips"),
        ],
    ),
    lambda: (
        "{-|} equip {^ed}",
        action(),
        [
            action(next_case=Case.CAP_FIRST_WORD),
            action(text="Equip", word="equip", trailing_space=" "),
            action(prev_attach=True, text="ped", trailing_space=" ", word="equipped"),
        ],
    ),
    lambda: (
        "{>} Equip",
        action(),
        [
            action(next_case=Case.LOWER_FIRST_CHAR),
            action(text="equip", word="Equip", trailing_space=" "),
        ],
    ),
    lambda: (
        "{>} equip",
        action(),
        [
            action(next_case=Case.LOWER_FIRST_CHAR),
            action(text_and_word="equip", trailing_space=" "),
        ],
    ),
    lambda: (
        "{<} equip",
        action(),
        [
            action(next_case=Case.UPPER_FIRST_WORD),
            action(text="EQUIP", word="equip", trailing_space=" ", upper_carry=True),
        ],
    ),
    lambda: (
        "{<} EQUIP",
        action(),
        [
            action(next_case=Case.UPPER_FIRST_WORD),
            action(text_and_word="EQUIP", trailing_space=" ", upper_carry=True),
        ],
    ),
    lambda: (
        "{<} equip {^ed}",
        action(),
        [
            action(next_case=Case.UPPER_FIRST_WORD),
            action(text="EQUIP", word="equip", trailing_space=" ", upper_carry=True),
            action(
                prev_attach=True,
                text="PED",
                trailing_space=" ",
                word="equipped",
                upper_carry=True,
            ),
        ],
    ),
    lambda: (
        "equip {*-|}",
        action(),
        [
            action(text_and_word="equip", trailing_space=" "),
            action(
                prev_attach=True,
                text="Equip",
                trailing_space=" ",
                word_and_prev_replace="equip",
            ),
        ],
    ),
    lambda: (
        "equip {^ed} {*-|}",
        action(),
        [
            action(text_and_word="equip", trailing_space=" "),
            action(prev_attach=True, text="ped", trailing_space=" ", word="equipped"),
            action(
                prev_attach=True,
                text="Equipped",
                trailing_space=" ",
                word_and_prev_replace="equipped",
            ),
        ],
    ),
    lambda: (
        "Equip {*>}",
        action(),
        [
            action(text_and_word="Equip", trailing_space=" "),
            action(
                prev_attach=True,
                text="equip",
                trailing_space=" ",
                word_and_prev_replace="Equip",
            ),
        ],
    ),
    lambda: (
        "Equip {^ed} {*>}",
        action(),
        [
            action(text_and_word="Equip", trailing_space=" "),
            action(prev_attach=True, text="ped", trailing_space=" ", word="Equipped"),
            action(
                prev_attach=True,
                text="equipped",
                trailing_space=" ",
                word_and_prev_replace="Equipped",
            ),
        ],
    ),
    lambda: (
        "equip {*<}",
        action(),
        [
            action(text_and_word="equip", trailing_space=" "),
            action(
                prev_attach=True,
                text="EQUIP",
                trailing_space=" ",
                word_and_prev_replace="equip",
            ),
        ],
    ),
    lambda: (
        "equip {^ed} {*<}",
        action(),
        [
            action(text_and_word="equip", trailing_space=" "),
            action(prev_attach=True, text="ped", trailing_space=" ", word="equipped"),
            action(
                prev_attach=True,
                text="EQUIPPED",
                trailing_space=" ",
                word_and_prev_replace="equipped",
            ),
        ],
    ),
    lambda: (
        "notanumber {*($c)}",
        action(),
        [
            action(text_and_word="notanumber", trailing_space=" "),
            action(word="notanumber", trailing_space=" "),
        ],
    ),
    lambda: (
        "0 {*($c)}",
        action(),
        [
            action(text_and_word="0", trailing_space=" "),
            action(
                prev_attach=True,
                text="$0",
                word="0",
                trailing_space=" ",
                prev_replace="0",
            ),
        ],
    ),
    lambda: (
        "0.00 {*($c)}",
        action(),
        [
            action(text_and_word="0.00", trailing_space=" "),
            action(
                prev_attach=True,
                text="$0.00",
                word="0.00",
                trailing_space=" ",
                prev_replace="0.00",
            ),
        ],
    ),
    lambda: (
        "1234 {*($c)}",
        action(),
        [
            action(text_and_word="1234", trailing_space=" "),
            action(
                prev_attach=True,
                text="$1,234",
                word="1,234",
                trailing_space=" ",
                prev_replace="1234",
            ),
        ],
    ),
    lambda: (
        "1234567 {*($c)}",
        action(),
        [
            action(text_and_word="1234567", trailing_space=" "),
            action(
                prev_attach=True,
                text="$1,234,567",
                word="1,234,567",
                trailing_space=" ",
                prev_replace="1234567",
            ),
        ],
    ),
    lambda: (
        "1234.5 {*($c)}",
        action(),
        [
            action(text_and_word="1234.5", trailing_space=" "),
            action(
                prev_attach=True,
                text="$1,234.50",
                word="1,234.50",
                trailing_space=" ",
                prev_replace="1234.5",
            ),
        ],
    ),
    lambda: (
        "1234.56 {*($c)}",
        action(),
        [
            action(text_and_word="1234.56", trailing_space=" "),
            action(
                prev_attach=True,
                text="$1,234.56",
                word="1,234.56",
                trailing_space=" ",
                prev_replace="1234.56",
            ),
        ],
    ),
    lambda: (
        "1234.567 {*($c)}",
        action(),
        [
            action(text_and_word="1234.567", trailing_space=" "),
            action(
                prev_attach=True,
                text="$1,234.57",
                word="1,234.57",
                trailing_space=" ",
                prev_replace="1234.567",
            ),
        ],
    ),
    lambda: (
        "equip {^} {^ed}",
        action(),
        [
            action(text_and_word="equip", trailing_space=" "),
            action(
                prev_attach=True,
                text="",
                word="equip",
                next_attach=True,
                orthography=False,
            ),
            action(prev_attach=True, text="ed", trailing_space=" ", word="equiped"),
        ],
    ),
    lambda: (
        "{prefix^} test {^ing}",
        action(),
        [
            action(text_and_word="prefix", next_attach=True),
            action(prev_attach=True, text_and_word="test", trailing_space=" "),
            action(prev_attach=True, text="ing", trailing_space=" ", word="testing"),
        ],
    ),
    lambda: (
        "{two prefix^} test {^ing}",
        action(),
        [
            action(text="two prefix", word="prefix", next_attach=True),
            action(prev_attach=True, text_and_word="test", trailing_space=" "),
            action(prev_attach=True, text="ing", trailing_space=" ", word="testing"),
        ],
    ),
    lambda: (
        "{-|}{^|~|^}",
        action(),
        [
            action(next_case=Case.CAP_FIRST_WORD),
            action(prev_attach=True, text_and_word="|~|", next_attach=True),
        ],
    ),
    lambda: (
        "{-|}{~|'^}cause",
        action(),
        [
            action(next_case=Case.CAP_FIRST_WORD),
            action(text_and_word="'", next_attach=True, next_case=Case.CAP_FIRST_WORD),
            action(prev_attach=True, text="Cause", trailing_space=" ", word="cause"),
        ],
    ),
    lambda: (
        "{.}{~|'^}cuz",
        action(),
        [
            action(
                prev_attach=True,
                text_and_word=".",
                trailing_space=" ",
                next_case=Case.CAP_FIRST_WORD,
            ),
            action(text_and_word="'", next_attach=True, next_case=Case.CAP_FIRST_WORD),
            action(prev_attach=True, text="Cuz", trailing_space=" ", word="cuz"),
        ],
    ),
    lambda: (
        "{.}{~|'^}cause",
        action(),
        [
            action(
                prev_attach=True,
                text_and_word=".",
                trailing_space=" ",
                next_case=Case.CAP_FIRST_WORD,
            ),
            action(text_and_word="'", next_attach=True, next_case=Case.CAP_FIRST_WORD),
            action(prev_attach=True, text="Cause", trailing_space=" ", word="cause"),
        ],
    ),
    lambda: (
        '{.}{^~|"}heyyo',
        action(),
        [
            action(
                prev_attach=True,
                text_and_word=".",
                trailing_space=" ",
                next_case=Case.CAP_FIRST_WORD,
            ),
            action(
                prev_attach=True,
                text_and_word='"',
                trailing_space=" ",
                next_case=Case.CAP_FIRST_WORD,
            ),
            action(text="Heyyo", trailing_space=" ", word="heyyo"),
        ],
    ),
    lambda: (
        "{.}{^~|^}zshrc",
        action(),
        [
            action(
                prev_attach=True,
                text_and_word=".",
                trailing_space=" ",
                next_case=Case.CAP_FIRST_WORD,
            ),
            action(
                prev_attach=True,
                text_and_word="",
                next_attach=True,
                next_case=Case.CAP_FIRST_WORD,
            ),
            action(prev_attach=True, text="Zshrc", trailing_space=" ", word="zshrc"),
        ],
    ),
    lambda: (
        "{.}",
        action(),
        [
            action(
                prev_attach=True,
                text_and_word=".",
                trailing_space=" ",
                next_case=Case.CAP_FIRST_WORD,
            )
        ],
    ),
    lambda: (
        "{,}",
        action(),
        [action(prev_attach=True, text_and_word=",", trailing_space=" ")],
    ),
    lambda: (
        "test{prefix^}",
        action(),
        [
            action(text_and_word="test", trailing_space=" "),
            action(text_and_word="prefix", next_attach=True),
        ],
    ),
    lambda: (
        "{prefix^}{prefix^}",
        action(),
        [
            action(text_and_word="prefix", next_attach=True),
            action(
                prev_attach=True, text="prefix", word="prefixprefix", next_attach=True
            ),
        ],
    ),
    lambda: (
        "{prefix^}{^ing}",
        action(),
        [
            action(text_and_word="prefix", next_attach=True),
            action(prev_attach=True, text="ing", trailing_space=" ", word="prefixing"),
        ],
    ),
    lambda: (
        "{prefix^}cancel{^ing}",
        action(),
        [
            action(text_and_word="prefix", next_attach=True),
            action(prev_attach=True, text="cancel", trailing_space=" ", word="cancel"),
            action(prev_attach=True, text="ing", trailing_space=" ", word="canceling"),
        ],
    ),
)


@parametrize(TRANSLATION_TO_ACTIONS_TESTS)
def test_translation_to_actions(translation, last_action, expected):
    ctx = formatting._Context([], action())
    ctx.translated(last_action)
    assert formatting._translation_to_actions(translation, ctx) == expected


RAW_TO_ACTIONS_TESTS = (
    lambda: (
        "2-6",
        action(),
        [action(glue=True, text_and_word="26", trailing_space=" ")],
    ),
    lambda: ("2", action(), [action(glue=True, text_and_word="2", trailing_space=" ")]),
    lambda: (
        "-8",
        action(),
        [action(glue=True, text_and_word="8", trailing_space=" ")],
    ),
    lambda: (
        "-68",
        action(),
        [action(glue=True, text_and_word="68", trailing_space=" ")],
    ),
    lambda: ("S-T", action(), [action(text_and_word="S-T", trailing_space=" ")]),
)


@parametrize(RAW_TO_ACTIONS_TESTS)
def test_raw_to_actions(stroke, last_action, expected):
    ctx = formatting._Context([], action())
    ctx.translated(last_action)
    assert formatting._raw_to_actions(stroke, ctx) == expected


ATOM_TO_ACTION_TESTS = (
    lambda: (
        "{^ed}",
        action(text_and_word="test", trailing_space=" "),
        action(prev_attach=True, text="ed", trailing_space=" ", word="tested"),
    ),
    lambda: (
        "{^ed}",
        action(text_and_word="carry", trailing_space=" "),
        action(
            prev_attach=True,
            text="ied",
            trailing_space=" ",
            prev_replace="y",
            word="carried",
        ),
    ),
    lambda: (
        "{^er}",
        action(text_and_word="test", trailing_space=" "),
        action(prev_attach=True, text="er", trailing_space=" ", word="tester"),
    ),
    lambda: (
        "{^er}",
        action(text_and_word="carry", trailing_space=" "),
        action(
            prev_attach=True,
            text="ier",
            trailing_space=" ",
            prev_replace="y",
            word="carrier",
        ),
    ),
    lambda: (
        "{^ing}",
        action(text_and_word="test", trailing_space=" "),
        action(prev_attach=True, text="ing", trailing_space=" ", word="testing"),
    ),
    lambda: (
        "{^ing}",
        action(text_and_word="begin", trailing_space=" "),
        action(prev_attach=True, text="ning", trailing_space=" ", word="beginning"),
    ),
    lambda: (
        "{^ing}",
        action(text_and_word="parade", trailing_space=" "),
        action(
            prev_attach=True,
            text="ing",
            trailing_space=" ",
            prev_replace="e",
            word="parading",
        ),
    ),
    lambda: (
        "{^s}",
        action(text_and_word="test", trailing_space=" "),
        action(prev_attach=True, text="s", trailing_space=" ", word="tests"),
    ),
    lambda: (
        "{,}",
        action(text_and_word="test", trailing_space=" "),
        action(prev_attach=True, text_and_word=",", trailing_space=" "),
    ),
    lambda: (
        "{:}",
        action(text_and_word="test", trailing_space=" "),
        action(prev_attach=True, text_and_word=":", trailing_space=" "),
    ),
    lambda: (
        "{;}",
        action(text_and_word="test", trailing_space=" "),
        action(prev_attach=True, text_and_word=";", trailing_space=" "),
    ),
    lambda: (
        "{.}",
        action(prev_attach=True, word="test", trailing_space=" "),
        action(
            prev_attach=True,
            text_and_word=".",
            trailing_space=" ",
            next_case=Case.CAP_FIRST_WORD,
        ),
    ),
    lambda: (
        "{?}",
        action(text_and_word="test", trailing_space=" "),
        action(
            prev_attach=True,
            text_and_word="?",
            trailing_space=" ",
            next_case=Case.CAP_FIRST_WORD,
        ),
    ),
    lambda: (
        "{!}",
        action(text_and_word="test", trailing_space=" "),
        action(
            prev_attach=True,
            text_and_word="!",
            trailing_space=" ",
            next_case=Case.CAP_FIRST_WORD,
        ),
    ),
    lambda: (
        "{-|}",
        action(text_and_word="test", trailing_space=" "),
        action(next_case=Case.CAP_FIRST_WORD, word="test", trailing_space=" "),
    ),
    lambda: (
        "{>}",
        action(text_and_word="test", trailing_space=" "),
        action(next_case=Case.LOWER_FIRST_CHAR, word="test", trailing_space=" "),
    ),
    lambda: (
        "{<}",
        action(text_and_word="test", trailing_space=" "),
        action(next_case=Case.UPPER_FIRST_WORD, word="test", trailing_space=" "),
    ),
    lambda: (
        "{*-|}",
        action(text_and_word="test", trailing_space=" "),
        action(
            prev_attach=True,
            text="Test",
            trailing_space=" ",
            word_and_prev_replace="test",
        ),
    ),
    lambda: (
        "{*>}",
        action(text_and_word="test", trailing_space=" "),
        action(
            prev_attach=True, text_and_word_and_prev_replace="test", trailing_space=" "
        ),
    ),
    lambda: (
        "{*<}",
        action(text_and_word="test", trailing_space=" "),
        action(
            prev_attach=True,
            text="TEST",
            word_and_prev_replace="test",
            trailing_space=" ",
        ),
    ),
    lambda: (
        "{PLOVER:test_command}",
        action(text_and_word="test", trailing_space=" "),
        action(word="test", command="test_command", trailing_space=" "),
    ),
    lambda: (
        "{&glue_text}",
        action(text_and_word="test", trailing_space=" "),
        action(text_and_word="glue_text", trailing_space=" ", glue=True),
    ),
    lambda: (
        "{&glue_text}",
        action(text_and_word="test", trailing_space=" ", glue=True),
        action(
            prev_attach=True,
            text="glue_text",
            trailing_space=" ",
            word="testglue_text",
            glue=True,
        ),
    ),
    lambda: (
        "{&glue_text}",
        action(text_and_word="test", next_attach=True),
        action(
            prev_attach=True,
            text="glue_text",
            trailing_space=" ",
            word="glue_text",
            glue=True,
        ),
    ),
    lambda: (
        "{^attach_text}",
        action(text_and_word="test", trailing_space=" "),
        action(
            prev_attach=True,
            text="attach_text",
            trailing_space=" ",
            word="testattach_text",
        ),
    ),
    lambda: (
        "{^attach_text^}",
        action(text_and_word="test", trailing_space=" "),
        action(
            prev_attach=True,
            text="attach_text",
            word="testattach_text",
            next_attach=True,
        ),
    ),
    lambda: (
        "{attach_text^}",
        action(text_and_word="test", trailing_space=" "),
        action(text_and_word="attach_text", next_attach=True),
    ),
    lambda: (
        "{#ALT_L(A)}",
        action(text_and_word="test", trailing_space=" "),
        action(combo="ALT_L(A)", trailing_space=" ", word="test"),
    ),
    lambda: (
        "text",
        action(text_and_word="test", trailing_space=" "),
        action(text_and_word="text", trailing_space=" "),
    ),
    lambda: (
        "text",
        action(text_and_word="test", trailing_space=" ", glue=True),
        action(text_and_word="text", trailing_space=" "),
    ),
    lambda: (
        "text",
        action(text_and_word="test", next_attach=True),
        action(prev_attach=True, text_and_word="text", trailing_space=" "),
    ),
    lambda: (
        "text",
        action(text_and_word="test", trailing_space=" ", next_case=Case.CAP_FIRST_WORD),
        action(text="Text", trailing_space=" ", word="text"),
    ),
    lambda: (
        "some text",
        action(text_and_word="test", trailing_space=" "),
        action(text="some text", trailing_space=" ", word="text"),
    ),
    lambda: (
        "some text",
        action(
            text_and_word="test", trailing_space=" ", case=Case.TITLE, space_char=""
        ),
        action(text="SomeText", word="text", case=Case.TITLE, space_char=""),
    ),
    lambda: (
        "some text",
        action(
            text_and_word="test",
            trailing_space=" ",  # This is camel case
            case=Case.TITLE,
            space_char="",
            next_case=Case.LOWER_FIRST_CHAR,
        ),
        action(text="someText", word="text", case=Case.TITLE, space_char=""),
    ),
    lambda: (
        "some text",
        action(text_and_word="test", trailing_space=" ", space_char="_"),
        action(text="some_text", trailing_space="_", word="text", space_char="_"),
    ),
    lambda: (
        "some text",
        action(text_and_word="test", trailing_space=" ", case=Case.UPPER),
        action(text="SOME TEXT", trailing_space=" ", word="text", case=Case.UPPER),
    ),
    lambda: (
        "sOme TexT",
        action(text_and_word="test", trailing_space=" ", case=Case.LOWER),
        action(text="some text", trailing_space=" ", word="TexT", case=Case.LOWER),
    ),
    lambda: (
        "sOme TexT",
        action(text_and_word="test", trailing_space=" ", case=Case.TITLE),
        action(text="Some Text", trailing_space=" ", word="TexT", case=Case.TITLE),
    ),
    lambda: (
        "{MODE:CAPS}",
        action(text_and_word="test", trailing_space=" "),
        action(word="test", trailing_space=" ", case=Case.UPPER),
    ),
    lambda: (
        "{MODE:LOWER}",
        action(text_and_word="test", trailing_space=" "),
        action(word="test", trailing_space=" ", case=Case.LOWER),
    ),
)


@parametrize(ATOM_TO_ACTION_TESTS)
def test_atom_to_action(atom, last_action, expected):
    ctx = formatting._Context((), last_action)
    ctx.translated(last_action)
    assert formatting._atom_to_action(atom, ctx) == expected


CHANGE_MODE_TESTS = (
    # Invalid modes.
    lambda: ("", action(), ValueError),
    lambda: ("ABCD", action(), ValueError),
    # CAPS: Uppercase
    lambda: ("CAPS", action(), action(case=Case.UPPER)),
    # LOWER: Lowercase
    lambda: ("LOWER", action(), action(case=Case.LOWER)),
    # TITLE: Titlecase
    lambda: ("TITLE", action(), action(case=Case.TITLE)),
    # CAMEL: Titlecase without space
    lambda: (
        "CAMEL",
        action(),
        action(case=Case.TITLE, space_char="", next_case=Case.LOWER_FIRST_CHAR),
    ),
    # SNAKE: Underscore space
    lambda: ("SNAKE", action(), action(space_char="_")),
    # RESET_SPACE: Default space
    lambda: ("RESET_SPACE", action(space_char="ABCD"), action()),
    # RESET_CASE: No case
    lambda: ("RESET_CASE", action(case=Case.UPPER), action()),
    # SET_SPACE:xy: Set space to xy
    lambda: ("SET_SPACE:", action(space_char="test"), action(space_char="")),
    lambda: ("SET_SPACE:-", action(space_char="test"), action(space_char="-")),
    lambda: (
        "SET_SPACE:123 45",
        action(space_char="test"),
        action(space_char="123 45"),
    ),
    # RESET: No case, default space
)


@parametrize(CHANGE_MODE_TESTS)
def test_meta_mode(meta, last_action, expected):
    atom = "{MODE:" + meta + "}"
    ctx = formatting._Context((), action())
    ctx.translated(last_action)
    if inspect.isclass(expected):
        with pytest.raises(expected):
            formatting._atom_to_action(atom, ctx)
    else:
        assert formatting._atom_to_action(atom, ctx) == expected


last_action_normal = action()
last_action_capitalized = action(next_case=Case.CAP_FIRST_WORD)
last_action_attached = action(next_attach=True)

META_CARRY_CAPITALIZE_TESTS = (
    # Test word handling and space handling, standard.
    lambda: (
        "~|*",
        last_action_normal,
        (action(word="*", text="*", trailing_space=" ")),
    ),
    # With attach flags:
    lambda: (
        "~|*^",
        last_action_normal,
        (action(word="*", text="*", next_attach=True)),
    ),
    lambda: (
        "^~|*",
        last_action_normal,
        (action(word="*", text="*", trailing_space=" ", prev_attach=True)),
    ),
    lambda: (
        "^~|*^",
        last_action_normal,
        (action(word="*", text="*", prev_attach=True, next_attach=True)),
    ),
    # Should 'do nothing'.
    lambda: ("~|", last_action_capitalized, (last_action_capitalized)),
    # Should lose 'next_attach' flag.
    lambda: ("~|", last_action_attached, (action(prev_attach=True))),
    # Verify capitalize carry.
    lambda: (
        "^~|^",
        last_action_capitalized,
        (
            action(
                next_case=Case.CAP_FIRST_WORD,
                text_and_word="",
                prev_attach=True,
                next_attach=True,
            )
        ),
    ),
    lambda: (
        "^~|aset^",
        last_action_capitalized,
        (
            action(
                next_case=Case.CAP_FIRST_WORD,
                prev_attach=True,
                next_attach=True,
                text="Aset",
                word="aset",
            )
        ),
    ),
    lambda: (
        "~|aset",
        last_action_capitalized,
        (
            action(
                next_case=Case.CAP_FIRST_WORD,
                text="Aset",
                trailing_space=" ",
                word="aset",
            )
        ),
    ),
    # Verify 'next_attach' flag overriding.
    lambda: (
        "~|aset",
        last_action_attached,
        (action(prev_attach=True, text_and_word="aset", trailing_space=" ")),
    ),
    lambda: (
        "~|aset^",
        last_action_attached,
        (action(prev_attach=True, text_and_word="aset", next_attach=True)),
    ),
)


@parametrize(META_CARRY_CAPITALIZE_TESTS)
def test_meta_carry_capitalize(meta, last_action, expected):
    ctx = formatting._Context((), action())
    ctx.translated(last_action)
    assert formatting._atom_to_action("{" + meta + "}", ctx) == expected


def _apply_case_tests():
    test = " some test "
    test2 = "test Me"
    test3 = " SOME TEST "
    return (
        # INVALID
        lambda: (test, "", False, ValueError),
        lambda: (test, "TEST", False, ValueError),
        # NO-OP
        lambda: (test, None, False, test),
        lambda: (test, None, True, test),
        # TITLE
        lambda: (test, Case.TITLE, False, " Some Test "),
        # TITLE will not affect appended output
        lambda: (test, Case.TITLE, True, " some test "),
        lambda: (test2, Case.TITLE, True, "test Me"),
        # LOWER
        lambda: (test, Case.LOWER, False, " some test "),
        lambda: (test3, Case.LOWER, False, " some test "),
        lambda: (test2, Case.LOWER, True, "test me"),
        # UPPER
        lambda: (test.upper(), Case.UPPER, False, " SOME TEST "),
        lambda: (test3, Case.UPPER, False, " SOME TEST "),
        lambda: (test2, Case.UPPER, True, "TEST ME"),
    )


@parametrize(_apply_case_tests())
def test_apply_case(input_text, case, appended, expected):
    if inspect.isclass(expected):
        with pytest.raises(expected):
            formatting.apply_mode_case(input_text, case, appended)
    else:
        assert formatting.apply_mode_case(input_text, case, appended) == expected


def _apply_space_char_tests():
    test = " some text "
    test2 = "don't"
    return (
        lambda: (test, "_", "_some_text_"),
        lambda: (test, "", "sometext"),
        lambda: (test2, "_", test2),
        lambda: (test2, "", test2),
    )


@parametrize(_apply_space_char_tests())
def test_apply_space_char(text, space_char, expected):
    assert formatting.apply_mode_space_char(text, space_char) == expected


@parametrize(
    (
        lambda: ("", None),
        lambda: ("{abc}", "abc"),
        lambda: ("abc", None),
    )
)
def test_get_meta(atom, meta):
    assert formatting._get_meta(atom) == meta


@parametrize(
    (
        lambda: ("abc", "{&abc}"),
        lambda: ("1", "{&1}"),
    )
)
def test_glue_translation(s, expected):
    assert formatting._glue_translation(s) == expected


@parametrize(
    (
        lambda: ("", ""),
        lambda: ("abc", "abc"),
        lambda: (r"\{", "{"),
        lambda: (r"\}", "}"),
        lambda: (r"\{abc\}}{", "{abc}}{"),
    )
)
def test_unescape_atom(atom, text):
    assert formatting._unescape_atom(atom) == text


@parametrize(
    (
        lambda: ("", ""),
        lambda: ("abc", "Abc"),
        lambda: ("ABC", "ABC"),
    )
)
def test_capitalize_first_word(s, expected):
    assert formatting.capitalize_first_word(s) == expected


RIGHTMOST_WORD_TESTS = (
    lambda: ("", ""),
    lambda: ("\n", ""),
    lambda: ("\t", ""),
    lambda: ("abc", "abc"),
    lambda: ("a word", "word"),
    lambda: ("word.", "."),
    lambda: ("word ", ""),
    lambda: ("word\n", ""),
    lambda: ("word\t", ""),
    lambda: (" word", "word"),
    lambda: ("\nword", "word"),
    lambda: ("\tword", "word"),
)


@parametrize(RIGHTMOST_WORD_TESTS)
def test_rightmost_word(s, expected):
    assert formatting.rightmost_word(s) == expected


REPLACE_TESTS = (
    # Check that 'prev_replace' does not unconditionally erase
    # the previous character if it does not match.
    lambda: (
        [
            translation(english="{MODE:SET_SPACE:}"),
            translation(english="foobar"),
            translation(english="{^}{#Return}{^}{-|}"),
        ],
        [("s", "foobar"), ("c", "Return")],
    ),
    # Check 'prev_replace' correctly takes into account
    # the previous translation.
    lambda: (
        [
            translation(english="test "),
            translation(english="{^,}"),
        ],
        [("s", "test "), ("b", 1), ("s", ", ")],
    ),
    # While the previous translation must be taken into account,
    # any meta-command must not be fired again.
    lambda: (
        [
            translation(english="{#Return}"),
            translation(english="test"),
        ],
        [("c", "Return"), ("s", "test ")],
    ),
)


@parametrize(REPLACE_TESTS)
def test_replace(translations, expected_instructions):
    output = CaptureOutput()
    formatter = formatting.Formatter()
    formatter.set_output(output)
    formatter.set_space_placement(SPACE_PLACEMENT_AFTER)
    prev = []
    for t in translations:
        formatter.format([], [t], prev)
        prev.append(t)
    assert output.instructions == expected_instructions


def test_undo_replace():
    # Undoing a replace....
    output = CaptureOutput()
    formatter = formatting.Formatter()
    formatter.set_output(output)
    formatter.set_space_placement(SPACE_PLACEMENT_AFTER)
    prev = [translation(english="test")]
    formatter.format([], prev, None)
    undo = translation(english="{^,}")
    formatter.format([], [undo], prev)
    # Undo.
    formatter.format([undo], [], prev)
    assert output.instructions == [
        ("s", "test "),
        ("b", 1),
        ("s", ", "),
        ("b", 2),
        ("s", " "),
    ]


OUTPUT_OPTIMISATION_TESTS = (
    # No change.
    lambda: (
        [
            translation(english="noop"),
        ],
        [
            translation(english="noop"),
        ],
        [("s", " noop")],
    ),
    # Append only.
    lambda: (
        [
            translation(english="test"),
        ],
        [
            translation(english="testing"),
        ],
        [("s", " test"), ("s", "ing")],
    ),
    # Chained meta-commands.
    lambda: (
        [
            translation(english="{#a}"),
        ],
        [
            translation(english="{#a}{#b}"),
        ],
        [("c", "a"), ("c", "b")],
    ),
)


@parametrize(OUTPUT_OPTIMISATION_TESTS)
def test_output_optimization(undo, do, expected_instructions):
    output = CaptureOutput()
    formatter = formatting.Formatter()
    formatter.set_output(output)
    formatter.format([], undo, None)
    formatter.format(undo, do, None)
    assert output.instructions == expected_instructions


class TestRetroFormatter:
    def setup_method(self):
        self.formatter = formatting.Formatter()
        self.translations = []
        self.retro_formatter = formatting.RetroFormatter(self.translations)

    def format(self, text):
        t = translation(english=text)
        self.formatter.format([], [t], self.translations)
        self.translations.append(t)
        return t

    ITER_LAST_ACTIONS_TESTS = (
        lambda: (
            ["Luca", "mela"],
            [
                action(text_and_word="mela", trailing_space=" "),
                action(text_and_word="Luca", trailing_space=" "),
            ],
        ),
        lambda: (
            ["{Luca^}", "{^mela}"],
            [
                action(
                    prev_attach=True, text="mela", trailing_space=" ", word="Lucamela"
                ),
                action(text_and_word="Luca", next_attach=True),
            ],
        ),
        lambda: (
            ["Luca", "{^ ^}", "mela"],
            [
                action(text_and_word="mela", trailing_space=" ", prev_attach=True),
                action(text=" ", word="", prev_attach=True, next_attach=True),
                action(text_and_word="Luca", trailing_space=" "),
            ],
        ),
        lambda: (
            ["Luca", "{-|}", "mela"],
            [
                action(text="Mela", trailing_space=" ", word="mela"),
                action(word="Luca", trailing_space=" ", next_case=Case.CAP_FIRST_WORD),
                action(text_and_word="Luca", trailing_space=" "),
            ],
        ),
    )

    @parametrize(ITER_LAST_ACTIONS_TESTS)
    def test_iter_last_actions(self, translation_list, action_list):
        for t in translation_list:
            self.format(t)
        assert list(self.retro_formatter.iter_last_actions()) == action_list

    ITER_LAST_FRAGMENTS_TESTS = (
        lambda: (False, ["Luca", "mela"], ["mela", "Luca "]),
        lambda: (False, ["Luca{^ ^}mela"], ["mela", "Luca "]),
        lambda: (False, ["Luca, mela."], ["mela.", "Luca, "]),
        lambda: (False, ["Luca{-|}mela"], ["Mela", "Luca "]),
        lambda: (True, ["Luca{-|}mela"], ["Mela", "Luca "]),
    )

    @parametrize(ITER_LAST_FRAGMENTS_TESTS)
    def test_iter_last_fragments(self, spaces_after, translation_list, fragment_list):
        if spaces_after:
            self.formatter.set_space_placement(SPACE_PLACEMENT_AFTER)
        for t in translation_list:
            self.format(t)
        assert list(self.retro_formatter.iter_last_fragments()) == fragment_list

    ITER_LAST_WORDS_TESTS = (
        lambda: (False, ["Luca", "mela"], ["mela", "Luca "]),
        lambda: (False, ["Luca{^ ^}mela"], ["mela", "Luca "]),
        lambda: (False, ["Luca, mela."], [".", "mela", ", ", "Luca"]),
        lambda: (False, ["Luca{-|}mela"], ["Mela", "Luca "]),
        lambda: (True, ["Luca{-|}mela"], ["Mela", "Luca "]),
    )

    @parametrize(ITER_LAST_WORDS_TESTS)
    def test_iter_last_words(self, spaces_after, translation_list, word_list):
        if spaces_after:
            self.formatter.set_space_placement(SPACE_PLACEMENT_AFTER)
        for t in translation_list:
            self.format(t)
        assert list(self.retro_formatter.iter_last_words()) == word_list

    LAST_TEXT_TESTS = (
        lambda: (False, ["Luca{-|}mela"], 3, "ela"),
        lambda: (False, ["Luca{-|}mela"], 5, " Mela"),
        lambda: (False, ["Luca{-|}mela"], 12, "Luca Mela"),
        lambda: (False, ["Luca{-|}mela"], 20, "Luca Mela"),
        lambda: (True, ["Luca{-|}mela"], 6, "a Mela"),
    )

    @parametrize(LAST_TEXT_TESTS)
    def test_last_text(self, spaces_after, translation_list, count, text):
        if spaces_after:
            self.formatter.set_space_placement(SPACE_PLACEMENT_AFTER)
        for t in translation_list:
            self.format(t)
        assert self.retro_formatter.last_text(count) == text
