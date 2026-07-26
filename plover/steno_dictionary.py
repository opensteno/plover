# Copyright (c) 2013 Hesky Fisher.
# See LICENSE.txt for details.

"""StenoDictionary class and related functions.

A steno dictionary maps sequences of steno strokes to translations.

"""

import collections
import os

from plover.resource import (
    ASSET_SCHEME,
    resource_filename,
    resource_timestamp,
    resource_update,
)


class StenoDictionary:
    """A steno dictionary.

    This dictionary maps immutable sequences to translations and tracks the
    length of the longest key.

    Attributes:
    longest_key -- A read only property holding the length of the longest key.
    timestamp -- File last modification time, used to detect external changes.

    """

    # False if class support creation.
    readonly = False

    def __init__(self):
        self._dict = {}
        self._longest_key = 0
        self.reverse = collections.defaultdict(list)
        # Case-insensitive reverse dict
        self.casereverse = collections.defaultdict(list)
        self.filters = []
        self.timestamp = 0
        self.readonly = False
        self.enabled = True
        self.path = None

    def __str__(self):
        return f"{self.__class__.__name__}({self.path!r})"

    def __repr__(self):
        return str(self)

    @classmethod
    def create(cls, resource):
        assert not resource.startswith(ASSET_SCHEME)
        if cls.readonly:
            raise ValueError(f"{cls.__name__} does not support creation")
        d = cls()
        d.path = resource
        return d

    @classmethod
    def load(cls, resource):
        filename = resource_filename(resource)
        timestamp = resource_timestamp(filename)
        d = cls()
        d._load(filename)
        if (
            cls.readonly
            or resource.startswith(ASSET_SCHEME)
            or not os.access(filename, os.W_OK)
        ):
            d.readonly = True
        d.path = resource
        d.timestamp = timestamp
        return d

    def save(self):
        assert not self.readonly
        with resource_update(self.path) as temp_path:
            self._save(temp_path)
        self.timestamp = resource_timestamp(self.path)

    def _load(self, filename):
        raise NotImplementedError()

    def _save(self, filename):
        raise NotImplementedError()

    @property
    def longest_key(self):
        """The length of the longest key in the dict."""
        return self._longest_key

    def __len__(self):
        return self._dict.__len__()

    def __iter__(self):
        return self._dict.__iter__()

    def __getitem__(self, key):
        return self._dict.__getitem__(key)

    def clear(self):
        assert not self.readonly
        self._dict.clear()
        self.reverse.clear()
        self.casereverse.clear()
        self._longest_key = 0

    def items(self):
        return self._dict.items()

    def update(self, *args, **kwargs):
        assert not self.readonly
        iterable_list = [
            a.items() if isinstance(a, (dict, StenoDictionary)) else a for a in args
        ]
        if kwargs:
            iterable_list.append(kwargs.items())
        if not self._dict:
            reverse = self.reverse
            casereverse = self.casereverse
            longest_key = self._longest_key
            assert not (reverse or casereverse or longest_key)
            self._dict = dict(*iterable_list)
            for key, value in self._dict.items():
                reverse[value].append(key)
                casereverse[value.lower()].append(value)
                key_len = len(key)
                longest_key = max(longest_key, key_len)
            self._longest_key = longest_key
        else:
            for iterable in iterable_list:
                for key, value in iterable:
                    self[key] = value

    def __setitem__(self, key, value):
        assert not self.readonly
        if key in self:
            del self[key]
        self._longest_key = max(self._longest_key, len(key))
        self._dict[key] = value
        self.reverse[value].append(key)
        self.casereverse[value.lower()].append(value)

    def get(self, key, fallback=None):
        return self._dict.get(key, fallback)

    def __delitem__(self, key):
        assert not self.readonly
        value = self._dict.pop(key)
        self.reverse[value].remove(key)
        self.casereverse[value.lower()].remove(value)
        if len(key) == self.longest_key:
            if self._dict:
                self._longest_key = max(len(x) for x in self._dict)
            else:
                self._longest_key = 0

    def __contains__(self, key):
        return self.get(key) is not None

    def reverse_lookup(self, value):
        return set(self.reverse.get(value, ()))

    def casereverse_lookup(self, value):
        return set(self.casereverse.get(value, ()))


class StenoDictionaryCollection:
    def __init__(self, dicts=()):
        self.dicts = []
        self.filters = []
        self.set_dicts(dicts)

    @property
    def longest_key(self):
        return max((d.longest_key for d in self.dicts if d.enabled), default=0)

    def set_dicts(self, dicts):
        self.dicts = list(dicts)

    def _lookup_keep_deleted(self, key, dicts=None, filters=()):
        """
        Lookup a key in the given dicts.
        If key appears in none of the dicts, return None.
        If key appears in some dicts but with "{plover:deleted}" as value,
        return "{plover:deleted}".
        """
        if dicts is None:
            dicts = self.dicts
        key_len = len(key)
        if key_len > self.longest_key:
            return None
        for d in dicts:
            if not d.enabled:
                continue
            if key_len > d.longest_key:
                continue
            value = d.get(key)
            if value is not None and not any(f(key, value) for f in filters):
                return value

    def _lookup(self, key, dicts=None, filters=()):
        """
        Same as _lookup_keep_deleted, but if key appears in some dicts
        but with "{plover:deleted}" as value (case-insensitive),
        return None instead.
        """
        result = self._lookup_keep_deleted(key, dicts, filters)
        if result is None or result.lower() == "{plover:deleted}":
            return None
        return result

    def _lookup_from_all(self, key, dicts=None, filters=()):
        """Key lookup from all dictionaries

        Returns list of (value, dictionary) tuples.
        Entries with value "{plover:deleted}" are kept.
        """
        if dicts is None:
            dicts = self.dicts
        key_len = len(key)
        if key_len > self.longest_key:
            return None
        values = []
        for d in dicts:
            if not d.enabled:
                continue
            if key_len > d.longest_key:
                continue
            value = d.get(key)
            if value and not any(f(key, value) for f in filters):
                values.append((value, d))
        return values

    def __str__(self):
        return "StenoDictionaryCollection" + repr(tuple(self.dicts))

    def __repr__(self):
        return str(self)

    def lookup(self, key):
        return self._lookup(key, filters=self.filters)

    def raw_lookup(self, key):
        return self._lookup(key)

    def lookup_from_all(self, key):
        return self._lookup_from_all(key, filters=self.filters)

    def raw_lookup_from_all(self, key):
        return self._lookup_from_all(key)

    def reverse_lookup(self, value):
        keys = set()
        for n, d in enumerate(self.dicts):
            if not d.enabled:
                continue
            # Ignore key if it's overridden by a higher priority dictionary.
            keys.update(
                k
                for k in d.reverse_lookup(value)
                if self._lookup_keep_deleted(k, dicts=self.dicts[:n]) is None
            )
        return keys

    def casereverse_lookup(self, value):
        keys = set()
        for d in self.dicts:
            if not d.enabled:
                continue
            keys.update(d.casereverse_lookup(value))
        return keys

    def first_writable(self):
        """Return the first writable dictionary."""
        for d in self.dicts:
            if not d.readonly:
                return d
        raise KeyError("no writable dictionary")

    def set(self, key, value, path=None):
        if path is None:
            d = self.first_writable()
        else:
            d = self[path]
        d[key] = value

    def save(self, path_list=None):
        """Save the dictionaries in <path_list>.

        If <path_list> is None, all writable dictionaries are saved"""
        if path_list is None:
            dict_list = [d for d in self if not d.readonly]
        else:
            dict_list = [self[path] for path in path_list]
        for d in dict_list:
            assert not d.readonly
            d.save()

    def get(self, path):
        for d in self.dicts:
            if d.path == path:
                return d

    def __getitem__(self, path):
        d = self.get(path)
        if d is None:
            raise KeyError(repr(path))
        return d

    def __iter__(self):
        for d in self.dicts:
            yield d.path

    def add_filter(self, f):
        self.filters.append(f)

    def remove_filter(self, f):
        self.filters.remove(f)
