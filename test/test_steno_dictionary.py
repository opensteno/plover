# Copyright (c) 2013 Hesky Fisher
# See LICENSE.txt for details.

"""Unit tests for steno_dictionary.py."""

import pytest

from plover.steno_dictionary import StenoDictionary, StenoDictionaryCollection

from plover_build_utils.testing import dictionary_test


def test_dictionary_collection():
    d1 = StenoDictionary()
    d1[("S",)] = "a"
    d1[("T",)] = "b"
    d1[("H",)] = "{PLOVER:deleted}"
    d1[("R",)] = "e"
    d1.path = "d1"
    d2 = StenoDictionary()
    d2[("S",)] = "c"
    d2[("W",)] = "d"
    d2[("H",)] = "f"
    d2[("R",)] = "{plover:deleted}"
    d2.path = "d2"
    dc = StenoDictionaryCollection([d2, d1])
    assert dc.lookup(("S",)) == "c"
    assert dc.lookup(("W",)) == "d"
    assert dc.lookup(("T",)) == "b"
    assert dc.lookup(("H",)) == "f"
    assert dc.lookup(("R",)) is None
    assert dc.lookup_from_all(("S",)) == [("c", d2), ("a", d1)]
    assert dc.lookup_from_all(("W",)) == [("d", d2)]
    assert dc.lookup_from_all(("T",)) == [("b", d1)]
    assert dc.lookup_from_all(("H",)) == [("f", d2), ("{PLOVER:deleted}", d1)]
    assert dc.lookup_from_all(("R",)) == [("{plover:deleted}", d2), ("e", d1)]

    def f(k, v):
        return v == "c"

    dc.add_filter(f)
    assert dc.lookup(("S",)) == "a"
    assert dc.raw_lookup(("S",)) == "c"
    assert dc.lookup_from_all(("S",)) == [("a", d1)]

    def g(k, v):
        return v == "a"

    dc.add_filter(g)
    assert dc.lookup(("S",)) is None
    assert dc.lookup_from_all(("S",)) == []
    assert dc.raw_lookup(("S",)) == "c"
    assert dc.lookup(("W",)) == "d"
    assert dc.lookup(("T",)) == "b"
    assert dc.raw_lookup(("W",)) == "d"
    assert dc.raw_lookup(("T",)) == "b"
    assert dc.raw_lookup_from_all(("S",)) == [("c", d2), ("a", d1)]
    assert dc.raw_lookup_from_all(("W",)) == [("d", d2)]
    assert dc.raw_lookup_from_all(("T",)) == [("b", d1)]
    assert dc.reverse_lookup("c") == {("S",)}

    dc.remove_filter(f)
    dc.remove_filter(g)
    assert dc.lookup(("S",)) == "c"
    assert dc.lookup(("W",)) == "d"
    assert dc.lookup(("T",)) == "b"
    assert dc.lookup(("H",)) == "f"
    assert dc.lookup(("R",)) is None
    assert dc.lookup_from_all(("S",)) == [("c", d2), ("a", d1)]
    assert dc.lookup_from_all(("W",)) == [("d", d2)]
    assert dc.lookup_from_all(("T",)) == [("b", d1)]
    assert dc.lookup_from_all(("H",)) == [("f", d2), ("{PLOVER:deleted}", d1)]
    assert dc.lookup_from_all(("R",)) == [("{plover:deleted}", d2), ("e", d1)]

    assert dc.reverse_lookup("c") == {("S",)}

    dc.set(("S",), "e")
    assert dc.lookup(("S",)) == "e"
    assert d2[("S",)] == "e"

    dc.set(("S",), "f", path="d1")
    assert dc.lookup(("S",)) == "e"
    assert d1[("S",)] == "f"
    assert d2[("S",)] == "e"

    # Iterating on a StenoDictionaryCollection is
    # the same as iterating on its dictionaries' paths.
    assert list(dc) == ["d2", "d1"]

    # Test get and [].
    assert dc.get("d1") == d1
    assert dc["d1"] == d1
    assert dc.get("invalid") is None
    with pytest.raises(KeyError):
        dc["invalid"]


def test_dictionary_collection_writeable():
    d1 = StenoDictionary()
    d1[("S",)] = "a"
    d1[("T",)] = "b"
    d2 = StenoDictionary()
    d2[("S",)] = "c"
    d2[("W",)] = "d"
    d2.readonly = True
    dc = StenoDictionaryCollection([d2, d1])
    assert dc.first_writable() == d1
    dc.set(("S",), "A")
    assert d1[("S",)] == "A"
    assert d2[("S",)] == "c"


def test_dictionary_collection_longest_key():
    k1 = ("S",)
    k2 = ("S", "T")
    k3 = ("S", "T", "R")

    dc = StenoDictionaryCollection()
    assert dc.longest_key == 0

    d1 = StenoDictionary()
    d1.path = "d1"
    d1[k1] = "a"

    dc.set_dicts([d1])
    assert dc.longest_key == 1

    d1[k2] = "a"
    assert dc.longest_key == 2

    d2 = StenoDictionary()
    d2.path = "d2"
    d2[k3] = "c"

    dc.set_dicts([d2, d1])
    assert dc.longest_key == 3

    del d1[k2]
    assert dc.longest_key == 3

    d2.enabled = False
    assert dc.longest_key == 1

    d1.enabled = False
    assert dc.longest_key == 0

    d2.enabled = True
    assert dc.longest_key == 3

    d1.enabled = True
    assert dc.longest_key == 3

    dc.set_dicts([d1])
    assert dc.longest_key == 1

    dc.set_dicts([])
    assert dc.longest_key == 0


def test_casereverse_lookup():
    dc = StenoDictionaryCollection()

    d1 = StenoDictionary()
    d1[("PWAOUFL",)] = "beautiful"
    d1[("WAOUFL",)] = "beAuTIFul"

    d2 = StenoDictionary()
    d2[("PW-FL",)] = "BEAUTIFUL"

    d3 = StenoDictionary()
    d3[("WAOUFL",)] = "not beautiful"

    dc.set_dicts([d1, d2, d3])

    assert dc.casereverse_lookup("beautiful") == {"beautiful", "BEAUTIFUL", "beAuTIFul"}


def test_reverse_lookup():
    dc = StenoDictionaryCollection()

    d1 = StenoDictionary()
    d1[("PWAOUFL",)] = "beautiful"
    d1[("WAOUFL",)] = "beautiful"

    d2 = StenoDictionary()
    d2[("PW-FL",)] = "beautiful"

    d3 = StenoDictionary()
    d3[("WAOUFL",)] = "not beautiful"

    # Simple test.
    dc.set_dicts([d1])
    assert dc.reverse_lookup("beautiful") == {("PWAOUFL",), ("WAOUFL",)}

    # No duplicates.
    d2_copy = StenoDictionary()
    d2_copy.update(d2)
    dc.set_dicts([d2_copy, d2])
    assert dc.reverse_lookup("beautiful") == {("PW-FL",)}

    # Don't stop at the first dictionary with matches.
    dc.set_dicts([d2, d1])
    assert dc.reverse_lookup("beautiful") == {("PW-FL",), ("PWAOUFL",), ("WAOUFL",)}

    # Ignore keys overridden by a higher precedence dictionary.
    dc.set_dicts([d3, d2, d1])
    assert dc.reverse_lookup("beautiful") == {("PW-FL",), ("PWAOUFL",)}


def test_dictionary_enabled():
    dc = StenoDictionaryCollection()
    d1 = StenoDictionary()
    d1.path = "d1"
    d1[("TEFT",)] = "test1"
    d1[("TEFGT",)] = "Testing"
    d2 = StenoDictionary()
    d2[("TEFT",)] = "test2"
    d2[("TEFT", "-G")] = "Testing"
    d2.path = "d2"
    dc.set_dicts([d2, d1])
    assert dc.lookup(("TEFT",)) == "test2"
    assert dc.raw_lookup(("TEFT",)) == "test2"
    assert dc.casereverse_lookup("testing") == {"Testing"}
    assert dc.reverse_lookup("Testing") == {("TEFT", "-G"), ("TEFGT",)}
    d2.enabled = False
    assert dc.lookup(("TEFT",)) == "test1"
    assert dc.raw_lookup(("TEFT",)) == "test1"
    assert dc.casereverse_lookup("testing") == {"Testing"}
    assert dc.reverse_lookup("Testing") == {("TEFGT",)}
    d1.enabled = False
    assert dc.lookup(("TEST",)) is None
    assert dc.raw_lookup(("TEFT",)) is None
    assert dc.casereverse_lookup("testing") == set()
    assert dc.reverse_lookup("Testing") == set()


@dictionary_test
class TestStenoDictionary:
    class DICT_CLASS(StenoDictionary):
        def _load(self, filename):
            pass

    DICT_EXTENSION = "dict"
    DICT_SAMPLE = b""


@dictionary_test
class TestReadOnlyStenoDictionary:
    class DICT_CLASS(StenoDictionary):
        readonly = True

        def _load(self, filename):
            pass

    DICT_EXTENSION = "dict"
    DICT_SAMPLE = b""
