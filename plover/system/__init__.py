from collections.abc import Sequence
import os
import re

from plover.oslayer.config import CONFIG_DIR
from plover.resource import resource_filename
from plover.registry import registry
from plover.steno import Stroke


def _load_wordlist(filename, assets_dir):
    if filename is None:
        return {}
    path = None
    for directory in (CONFIG_DIR, assets_dir):
        if directory is None:
            continue
        path = os.path.join(resource_filename(directory), filename)
        if os.path.exists(path):
            break
    else:
        return {}
    with open(path, encoding="utf-8") as f:
        text = f.read()
    fields = text.split()
    it = iter(fields)
    words = dict(zip(it, map(int, it)))
    assert len(fields) == 2 * len(words), path + " contains duplicate words."
    return words


def _key_order(keys, numbers):
    key_order = {}
    for order, key in enumerate(keys):
        key_order[key] = order
        number_key = numbers.get(key)
        if number_key is not None:
            key_order[number_key] = order
    return key_order


def _suffix_keys(keys):
    assert isinstance(keys, Sequence)
    return keys


_EXPORTS = {
    "KEYS": lambda mod: mod.KEYS,
    "KEY_ORDER": lambda mod: _key_order(mod.KEYS, mod.NUMBERS),
    "NUMBER_KEY": lambda mod: mod.NUMBER_KEY,
    "NUMBERS": lambda mod: dict(mod.NUMBERS),
    "FERAL_NUMBER_KEY": lambda mod: getattr(mod, "FERAL_NUMBER_KEY", False),
    "SUFFIX_KEYS": lambda mod: _suffix_keys(mod.SUFFIX_KEYS),
    "UNDO_STROKE_STENO": lambda mod: mod.UNDO_STROKE_STENO,
    "IMPLICIT_HYPHEN_KEYS": lambda mod: set(mod.IMPLICIT_HYPHEN_KEYS),
    "IMPLICIT_HYPHENS": lambda mod: {
        key.replace("-", "") for key in mod.IMPLICIT_HYPHEN_KEYS
    },
    "ORTHOGRAPHY_WORDS": lambda mod: _load_wordlist(
        mod.ORTHOGRAPHY_WORDLIST, mod.DICTIONARIES_ROOT
    ),
    "ORTHOGRAPHY_RULES": lambda mod: [
        (re.compile(pattern, re.IGNORECASE), replacement)
        for pattern, replacement in mod.ORTHOGRAPHY_RULES
    ],
    "ORTHOGRAPHY_RULES_ALIASES": lambda mod: dict(mod.ORTHOGRAPHY_RULES_ALIASES),
    "KEYMAPS": lambda mod: mod.KEYMAPS,
    "DICTIONARIES_ROOT": lambda mod: mod.DICTIONARIES_ROOT,
    "DEFAULT_DICTIONARIES": lambda mod: mod.DEFAULT_DICTIONARIES,
}


def setup(system_name):
    system_symbols = {}
    system_mod = registry.get_plugin("system", system_name).obj
    for symbol, init in _EXPORTS.items():
        system_symbols[symbol] = init(system_mod)
    system_symbols["NAME"] = system_name
    globals().update(system_symbols)
    Stroke.setup(
        system_symbols["KEYS"],
        system_symbols["IMPLICIT_HYPHEN_KEYS"],
        system_symbols["NUMBER_KEY"],
        system_symbols["NUMBERS"],
        system_symbols["FERAL_NUMBER_KEY"],
        system_symbols["UNDO_STROKE_STENO"],
    )


NAME = None
