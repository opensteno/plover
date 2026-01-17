"""
This module handles *keymaps*, mappings between keys on a physical machine and
*actions* that produce steno strokes for a certain steno system. Keymaps exist
for each combination of machine and system.

Keymaps are bidirectional, so we make a distinction between *bindings* and
*mappings*: a key is *bound* to an action, i.e. when a key is pressed Plover
performs the corresponding action, and an action is *mapped* to one or more
keys. Each action *should* be mapped to at least one key, and each key to an
action; otherwise, the behavior when stroking is undefined.
"""

from __future__ import annotations

import json
from collections import OrderedDict, defaultdict
from collections.abc import KeysView
from typing import Any

from plover import log


class Keymap:
    """
    Args:
        keys: A list of possible keys on the physical machine. For a serial steno
            protocol like TX Bolt, this would be the steno keys themselves
            (``S-``, ``T-``, etc.); for the keyboard, this would be keyboard keys
            (``q``, ``w``, etc.).
        actions: A list of possible actions in the steno system.

            In addition to the steno keys in the current system (see
            :attr:`system.KEYS<plover.system.KEYS>` for more information),
            the actions may include ``no-op``, a special action that does nothing,
            and ``arpeggiate``, a special action for arpeggiate mode that is only
            available if the current machine is a keyboard.
    """

    _actions: OrderedDict[str, int]
    _keys: OrderedDict[str, int]
    _mappings: OrderedDict[str, tuple[str, ...]]
    _bindings: dict[str, str]

    def __init__(
        self, keys: list[str] | tuple[str, ...], actions: list[str] | tuple[str, ...]
    ):
        # List of supported actions.
        self._actions = OrderedDict((action, n) for n, action in enumerate(actions))
        self._actions["no-op"] = len(self._actions)
        # List of supported keys.
        self._keys = OrderedDict((key, n) for n, key in enumerate(keys))
        # action -> keys
        self._mappings = {}
        # key -> action
        self._bindings = {}

    def get_keys(self) -> KeysView[str]:
        """Returns the list of possible keys."""
        return self._keys.keys()

    def get_actions(self) -> KeysView[str]:
        """Returns the list of possible actions."""
        return self._actions.keys()

    def set_bindings(self, bindings: dict[str, str]) -> None:
        """Use ``bindings`` as the new keymap.

        Args:
            bindings: A dictionary mapping *keys* to *actions*.

        Notes:
            This also calculates the mappings and calls :meth:`set_mappings`.
        """
        # Set from:
        # { key1: action1, key2: action1, ... keyn: actionn }
        mappings = defaultdict(list)
        for key, action in dict(bindings).items():
            mappings[action].append(key)
        self.set_mappings(mappings)

    def set_mappings(self, mappings: Any) -> None:
        """Use ``mappings`` as the new keymap.

        Args:
            mappings: A dictionary mapping *actions* to either a single key or a
                list of keys that are bound to that action. This also calculates
                the bindings and calls :meth:`set_bindings`.

        Warnings:
            Where ``mappings`` contains some consistency issues, such as keys bound
            multiple times or nonexistent keys or actions, this shows a warning and
            the keymap behavior is undefined.
        """
        # When setting from a string, assume a list of mappings:
        # [[action1, [key1, key2]], [action2, [key3]], ...]
        if isinstance(mappings, str):
            mappings = json.loads(mappings)
        mappings = dict(mappings)
        # Set from:
        # { action1: [key1, key2], ... actionn: [keyn] }
        self._mappings = OrderedDict()
        self._bindings = {}
        bound_keys = defaultdict(list)
        errors = []
        for action in self._actions:
            key_list = mappings.get(action)
            if not key_list:
                # Not an issue if 'no-op' is not mapped...
                if action != "no-op":
                    errors.append("action %s is not bound" % action)
                # Add dummy mapping for each missing action
                # so it's shown in the configurator.
                self._mappings[action] = ()
                continue
            if isinstance(key_list, str):
                key_list = (key_list,)
            valid_key_list = []
            for key in key_list:
                if key not in self._keys:
                    errors.append("invalid key %s bound to action %s" % (key, action))
                    continue
                valid_key_list.append(key)
                bound_keys[key].append(action)
                self._bindings[key] = action
            self._mappings[action] = tuple(sorted(valid_key_list, key=self._keys.get))
        for action in set(mappings) - set(self._actions):
            key_list = mappings.get(action)
            if isinstance(key_list, str):
                key_list = (key_list,)
            errors.append(
                "invalid action %s mapped to key(s) %s" % (action, " ".join(key_list))
            )
        for key, action_list in bound_keys.items():
            if len(action_list) > 1:
                errors.append(
                    "key %s is bound multiple times: %s" % (key, str(action_list))
                )
        if len(errors) > 0:
            log.warning(
                "Keymap is invalid, behavior undefined:\n\n- " + "\n- ".join(errors)
            )

    def get_bindings(self) -> dict[str, str]:
        """Returns the dictionary of bindings from keys to actions."""
        return self._bindings

    def get_mappings(self) -> OrderedDict[str, tuple[str, ...]]:
        """Returns the dictionary of mappings from actions to keys."""
        return self._mappings

    def get_action(self, key: str, default: str | None = None) -> str | None:
        """Given ``key``, returns the action, or ``default`` if unbound."""
        return self._bindings.get(key, default)

    def keys_to_actions(self, key_list: list[str] | tuple[str, ...]) -> list[str]:
        """Returns the actions performed by pressing all of the keys in ``key_list``.

        Raises an error if any element of ``key_list`` is not a valid machine
        key (i.e. not in the keys passed to :meth:`__init__`).
        """
        action_list = []
        for key in key_list:
            assert key in self._keys, "'%s' not in %s" % (key, self._keys)
            action = self._bindings[key]
            if "no-op" != action:
                action_list.append(action)
        return action_list

    def keys(self):
        return self._mappings.keys()

    def values(self):
        return self._mappings.values()

    def __len__(self):
        return len(self._mappings)

    def __getitem__(self, key):
        """Returns the list of keys that are bound to the action ``key``.

        (Confusing, I know.)
        """
        return self._mappings[key]

    def __setitem__(self, action, key_list):
        """Maps ``action`` to all the keys in ``key_list``.

        Also unbinds each key in ``key_list`` if already bound.
        """
        assert action in self._actions
        if isinstance(key_list, str):
            key_list = (key_list,)
        # Delete previous bindings.
        if action in self._mappings:
            for old_key in self._mappings[action]:
                if old_key in self._bindings:
                    del self._bindings[old_key]
        errors = []
        valid_key_list = []
        for key in key_list:
            if key not in self._keys:
                errors.append("invalid key %s bound to action %s" % (key, action))
                continue
            if key in self._bindings:
                errors.append(
                    "key %s is already bound to: %s" % (key, self._bindings[key])
                )
                continue
            valid_key_list.append(key)
            self._bindings[key] = action
        self._mappings[action] = tuple(sorted(valid_key_list, key=self._keys.get))
        if len(errors) > 0:
            log.warning(
                "Keymap is invalid, behavior undefined:\n\n- " + "\n- ".join(errors)
            )

    def __iter__(self):
        return iter(self._mappings)

    def __eq__(self, other):
        return self.get_mappings() == other.get_mappings()

    def __str__(self):
        # Use the more compact list of mappings format:
        # [[action1, [key1, key2]], [action2, [key3]], ...]
        return json.dumps(list(self._mappings.items()))
