# Copyright (c) 2013 Hesky Fisher
# See LICENSE.txt for details.

"""Tests for loading_manager.py."""

import os
import tempfile
from collections import defaultdict

import pytest

from plover.dictionary import loading_manager
from plover.engine import ErroredDictionary


class FakeDictionaryContents:
    def __init__(self, contents, timestamp):
        self.contents = contents
        self.timestamp = timestamp

    def __eq__(self, other):
        if isinstance(other, FakeDictionaryContents):
            return self.contents == other.contents
        return self.contents == other


class FakeDictionaryInfo:
    def __init__(self, name, contents):
        self.name = name
        self.contents = contents
        # Kept open for the lifetime of the fake dictionary.
        self.tf = tempfile.NamedTemporaryFile()  # noqa: SIM115

    def __repr__(self):
        return f"FakeDictionaryInfo({self.name!r}, {self.contents!r})"


class MockLoader:
    def __init__(self, files):
        self.files = files
        self.load_counts = defaultdict(int)

    def __call__(self, filename):
        self.load_counts[filename] += 1
        d = self.files[filename]
        if isinstance(d.contents, Exception):
            raise d.contents
        timestamp = os.path.getmtime(filename)
        return FakeDictionaryContents(d.contents, timestamp)


def test_loading(monkeypatch):
    dictionaries = {}
    for i in range(8):
        c = chr(ord("a") + i)
        contents = c * 5
        if i >= 4:
            contents = Exception(contents)
        d = FakeDictionaryInfo(c, contents)
        assert d.tf.name not in dictionaries
        dictionaries[d.tf.name] = d
        assert c not in dictionaries
        dictionaries[c] = d

    def df(name):
        return dictionaries[name].tf.name

    loader = MockLoader(dictionaries)
    monkeypatch.setattr("plover.dictionary.loading_manager.load_dictionary", loader)
    manager = loading_manager.DictionaryLoadingManager(lambda filename, result: None)
    manager.start_loading(df("a")).get()
    manager.start_loading(df("b")).get()
    results = manager.load([df("c"), df("b")])
    # Returns the right values in the right order.
    assert results == ["ccccc", "bbbbb"]
    # Dropped superfluous files.
    assert sorted([df("b"), df("c")]) == sorted(manager.dictionaries.keys())
    # Check dict like interface.
    assert len(manager) == 2
    assert df("a") not in manager
    with pytest.raises(KeyError):
        manager[df("a")]
    assert df("b") in manager
    assert df("c") in manager
    assert results == [manager[df("c")], manager[df("b")]]
    # Return a ErroredDictionary for load errors.
    results = manager.load([df("c"), df("e"), df("b"), df("f")])
    assert len(results) == 4
    assert results[0] == "ccccc"
    assert results[2] == "bbbbb"
    assert isinstance(results[1], ErroredDictionary)
    assert results[1].path == df("e")
    assert isinstance(results[1].exception, Exception)
    assert isinstance(results[3], ErroredDictionary)
    assert results[3].path == df("f")
    assert isinstance(results[3].exception, Exception)
    # Only loaded the files once.
    assert all(x == 1 for x in loader.load_counts.values())
    # No reload if file timestamp is unchanged, or the dictionary
    # timestamp is more recent. (use case: dictionary edited with
    # Plover and saved back)
    file_timestamp = results[0].timestamp
    results[0].timestamp = file_timestamp + 1
    dictionaries["c"].contents = "CCCCC"
    results = manager.load([df("c")])
    assert results == ["ccccc"]
    assert loader.load_counts[df("c")] == 1
    # Check outdated dictionaries are reloaded.
    results[0].timestamp = file_timestamp - 1
    results = manager.load([df("c")])
    assert results == ["CCCCC"]
    assert loader.load_counts[df("c")] == 2
    # Check trimming of outdated dictionaries.
    results[0].timestamp = file_timestamp - 1
    manager.unload_outdated()
    assert len(manager) == 0
    assert df("c") not in manager
