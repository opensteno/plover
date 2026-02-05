"""This module provides a skeleton for implementing keyboard input to grab steno
keystrokes. This is typically platform-specific, so actual implementations
are contained in platform-specific :mod:`oslayer <plover.oslayer>` modules.
"""

from __future__ import annotations

from collections.abc import Sequence


class Capture:
    """Encapsulates logic for capturing keyboard input. An instance of this is
    used internally by Plover's built-in keyboard plugin.

    Define the :meth:`key_down` and :meth:`key_up` methods below to implement
    custom behavior that gets executed when a key is pressed or released.
    """

    def start(self) -> None:
        """Start collecting keyboard input."""
        raise NotImplementedError()

    def cancel(self) -> None:
        """Stop collecting keyboard input."""
        raise NotImplementedError()

    def suppress(self, suppressed_keys: Sequence[str] = ()) -> None:
        """Suppresses the specified keys, preventing them from returning any
        output through regular typing. This allows us to intercept keyboard
        events when using keyboard input.
        """
        raise NotImplementedError()

    # Callbacks for keyboard press/release events.
    def key_down(self, key: str) -> None:
        """Notifies Plover that a key was pressed down."""
        return None

    def key_up(self, key: str) -> None:
        """Notifies Plover that a key was released."""
        return None
