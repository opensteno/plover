import pytest
from PySide6.QtGui import QValidator

from plover.gui_qt.steno_validator import StenoValidator


@pytest.mark.parametrize(
    ("text", "state"),
    (
        # Acceptable.
        ("ST", QValidator.State.Acceptable),
        ("TEFT", QValidator.State.Acceptable),
        ("TEFT/-G", QValidator.State.Acceptable),
        ("/ST", QValidator.State.Acceptable),
        ("-F", QValidator.State.Acceptable),
        # Intermediate.
        ("-", QValidator.State.Intermediate),
        ("/", QValidator.State.Intermediate),
        ("/-", QValidator.State.Intermediate),
        ("ST/", QValidator.State.Intermediate),
        ("ST/-", QValidator.State.Intermediate),
        ("ST//", QValidator.State.Intermediate),
        # Invalid.
        ("WK", QValidator.State.Invalid),
        ("PLOVER", QValidator.State.Invalid),
    ),
)
def test_steno_validator_validate(text, state):
    validator = StenoValidator()
    assert validator.validate(text, len(text)) == (state, text, len(text))
