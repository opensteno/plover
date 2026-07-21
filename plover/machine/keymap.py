import json
from collections import defaultdict, OrderedDict

from plover import log


class Keymap:
    def __init__(self, keys, actions):
        # List of supported actions.
        self._actions = OrderedDict((action, n) for n, action in enumerate(actions))
        self._actions["no-op"] = len(self._actions)
        # List of supported keys.
        self._keys = OrderedDict((key, n) for n, key in enumerate(keys))
        # action -> keys
        self._mappings = {}
        # key -> action
        self._bindings = {}

    def get_keys(self):
        return self._keys.keys()

    def get_actions(self):
        return self._actions.keys()

    def set_bindings(self, bindings):
        # Set from:
        # { key1: action1, key2: action1, ... keyn: actionn }
        mappings = defaultdict(list)
        for key, action in dict(bindings).items():
            mappings[action].append(key)
        self.set_mappings(mappings)

    def set_mappings(self, mappings):
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

    def get_bindings(self):
        return self._bindings

    def get_mappings(self):
        return self._mappings

    def get_action(self, key, default=None):
        return self._bindings.get(key, default)

    def keys_to_actions(self, key_list):
        action_list = []
        for key in key_list:
            assert key in self._keys, "'%s' not in %s" % (key, self._keys)
            action = self._bindings.get(key, "no-op")
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
        return self._mappings[key]

    def __setitem__(self, action, key_list):
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
