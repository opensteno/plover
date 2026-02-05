from collections import defaultdict
from contextlib import contextmanager
import ast
import functools
import inspect
import os

import pytest

from plover.registry import registry
from plover.resource import ASSET_SCHEME
from plover.steno import normalize_steno
from plover.steno_dictionary import StenoDictionary

from .dict import make_dict
from .parametrize import parametrize


class _DictionaryTests:
    @staticmethod
    def make_dict(contents):
        return contents

    @contextmanager
    def tmp_dict(self, tmp_path, contents):
        contents = self.make_dict(contents)
        with make_dict(tmp_path, contents, extension=self.DICT_EXTENSION) as dict_path:
            yield dict_path

    @contextmanager
    def sample_dict(self, tmp_path):
        with self.tmp_dict(tmp_path, self.DICT_SAMPLE) as dict_path:
            yield dict_path

    @staticmethod
    def parse_entries(entries):
        return {
            normalize_steno(k): v
            for k, v in ast.literal_eval("{" + entries + "}").items()
        }

    def test_readonly_writable_file(self, tmp_path):
        """
        Writable file: match class read-only attribute.
        """
        with self.sample_dict(tmp_path) as dict_path:
            d = self.DICT_CLASS.load(str(dict_path))
            assert d.readonly == self.DICT_CLASS.readonly

    def test_readonly_readonly_file(self, tmp_path):
        """
        Read-only file: read-only dictionary.
        """
        with self.sample_dict(tmp_path) as dict_path:
            dict_path.chmod(0o440)
            try:
                d = self.DICT_CLASS.load(str(dict_path))
                assert d.readonly
            finally:
                # Deleting the file will fail on Windows
                # if we don't restore write permission.
                dict_path.chmod(0o660)

    def test_readonly_asset(self, tmp_path, monkeypatch):
        """
        Assets are always read-only.
        """
        with self.sample_dict(tmp_path) as dict_path:
            fake_asset = ASSET_SCHEME + "fake:" + dict_path.name

            def fake_asset_only(r, v=None):
                assert r.startswith(ASSET_SCHEME + "fake:")
                return v

            monkeypatch.setattr(
                "plover.resource._asset_filename",
                functools.partial(fake_asset_only, v=str(dict_path)),
            )
            d = self.DICT_CLASS.load(fake_asset)
        assert d.readonly

    VALID_KEY = ("TEFT", "-G")

    @pytest.mark.parametrize(
        "method_name, args",
        (
            ("__delitem__", (VALID_KEY,)),
            ("__setitem__", (VALID_KEY, "pouet!")),
            ("clear", ()),
            ("save", ()),
            ("update", ()),
        ),
    )
    def test_readonly_no_change_allowed(self, tmp_path, method_name, args):
        """
        Don't allow changing a read-only dictionary.
        """
        with self.sample_dict(tmp_path) as dict_path:
            d = self.DICT_CLASS.load(str(dict_path))
        d.readonly = True
        method = getattr(d, method_name)
        with pytest.raises(AssertionError):
            method(*args)

    def _test_entrypoint(self):
        """
        Check a corresponding `plover.dictionary` entrypoint exists.
        """
        plugin = registry.get_plugin("dictionary", self.DICT_EXTENSION)
        assert plugin.obj == self.DICT_CLASS

    DUMMY = object()
    MISSING_KEY = "ceci n'est pas une clef"
    MISSING_TRANSLATION = "ceci n'est pas une translation"

    def _test_load(self, tmp_path, contents, expected):
        """
        Test `load` implementation.
        """
        with self.tmp_dict(tmp_path, contents) as dict_path:
            expected_timestamp = dict_path.stat().st_mtime
            if inspect.isclass(expected):
                # Expect an exception.
                with pytest.raises(expected):
                    self.DICT_CLASS.load(str(dict_path))
                return
            # Except a successful load.
            d = self.DICT_CLASS.load(str(dict_path))
        # Parse entries:
        entries = self.parse_entries(expected)
        # - expected: must be present
        expected_entries = {k: v for k, v in entries.items() if v is not None}
        # - unexpected: must not be present
        unexpected_entries = {k for k, v in entries.items() if v is None}
        # Basic checks.
        assert d.readonly == self.DICT_CLASS.readonly
        assert d.timestamp == expected_timestamp
        if self.DICT_SUPPORT_SEQUENCE_METHODS:
            assert sorted(d.items()) == sorted(expected_entries.items())
            assert sorted(d) == sorted(expected_entries)
            assert len(d) == len(expected_entries)
        else:
            assert tuple(d.items()) == ()
            assert tuple(d) == ()
            assert len(d) == 0
        for k, v in expected_entries.items():
            assert k in d
            assert d[k] == v
            assert d.get(k) == v
            assert d.get(k, self.DUMMY) == v
        for k in unexpected_entries:
            assert k not in d
            with pytest.raises(KeyError):
                d[k]
            assert d.get(k) is None
            assert d.get(k, self.DUMMY) == self.DUMMY
        assert self.MISSING_KEY not in d
        assert d.get(self.MISSING_KEY, self.DUMMY) is self.DUMMY
        assert d.get(self.MISSING_KEY) is None
        with pytest.raises(KeyError):
            d[self.MISSING_KEY]
        # Longest key check.
        expected_longest_key = functools.reduce(
            max, (len(k) for k in expected_entries), 0
        )
        assert d.longest_key == expected_longest_key
        # Reverse lookup checks.
        expected_reverse = defaultdict(set)
        if self.DICT_SUPPORT_REVERSE_LOOKUP:
            for k, v in expected_entries.items():
                expected_reverse[v].add(k)
        for v, key_set in expected_reverse.items():
            assert d.reverse_lookup(v) == key_set
        assert d.reverse_lookup(self.MISSING_TRANSLATION) == set()
        # Case reverse lookup checks.
        expected_casereverse = defaultdict(set)
        if self.DICT_SUPPORT_CASEREVERSE_LOOKUP:
            for v in expected_entries.values():
                expected_casereverse[v.lower()].add(v)
        for v, value_set in expected_casereverse.items():
            assert d.casereverse_lookup(v) == value_set
        assert d.casereverse_lookup(self.MISSING_TRANSLATION) == set()


class _ReadOnlyDictionaryTests:
    def test_readonly_no_create_allowed(self, tmp_path):
        """
        Don't allow creating a read-only dictionary.
        """
        with self.sample_dict(tmp_path) as dict_path:
            with pytest.raises(ValueError):
                self.DICT_CLASS.create(str(dict_path))


_TEST_DICTIONARY_UPDATE_DICT = {
    ("S-G",): "something",
    ("SPH-G",): "something",
    ("SPH*G",): "Something",
    ("SPH", "THEUPBG"): "something",
}
_TEST_DICTIONARY_UPDATE_STENODICT = StenoDictionary()
_TEST_DICTIONARY_UPDATE_STENODICT.update(_TEST_DICTIONARY_UPDATE_DICT)


class _WritableDictionaryTests:
    def test_longest_key(self):
        """
        Check `longest_key` support.
        """
        assert self.DICT_SUPPORT_SEQUENCE_METHODS
        d = self.DICT_CLASS()
        assert d.longest_key == 0
        d[("S",)] = "a"
        assert d.longest_key == 1
        d[("S", "S", "S", "S")] = "b"
        assert d.longest_key == 4
        d[("S", "S")] = "c"
        assert d.longest_key == 4
        assert d[("S", "S")] == "c"
        del d[("S", "S", "S", "S")]
        assert d.longest_key == 2
        del d[("S",)]
        assert d.longest_key == 2
        if self.DICT_SUPPORT_REVERSE_LOOKUP:
            assert d.reverse_lookup("c") == {("S", "S")}
        else:
            assert d.reverse_lookup("c") == set()
        if self.DICT_SUPPORT_CASEREVERSE_LOOKUP:
            assert d.casereverse_lookup("c") == {"c"}
        else:
            assert d.casereverse_lookup("c") == set()
        d.clear()
        assert d.longest_key == 0
        assert d.reverse_lookup("c") == set()
        assert d.casereverse_lookup("c") == set()
        d[("S", "S")] = "c"
        assert d.longest_key == 2

    def test_casereverse_del(self):
        """
        Check deletion correctly updates `casereverse_lookup` data.
        """
        d = self.DICT_CLASS()
        d[("S-G",)] = "something"
        d[("SPH-G",)] = "something"
        if self.DICT_SUPPORT_CASEREVERSE_LOOKUP:
            assert d.casereverse_lookup("something") == {"something"}
        else:
            assert d.casereverse_lookup("something") == set()
        del d[("S-G",)]
        if self.DICT_SUPPORT_CASEREVERSE_LOOKUP:
            assert d.casereverse_lookup("something") == {"something"}
        else:
            assert d.casereverse_lookup("something") == set()
        del d[("SPH-G",)]
        assert d.casereverse_lookup("something") == set()

    @parametrize(
        (
            lambda: (dict(_TEST_DICTIONARY_UPDATE_DICT), False, True),
            lambda: (dict(_TEST_DICTIONARY_UPDATE_DICT), False, False),
            lambda: (list(_TEST_DICTIONARY_UPDATE_DICT.items()), False, True),
            lambda: (list(_TEST_DICTIONARY_UPDATE_DICT.items()), False, False),
            lambda: (list(_TEST_DICTIONARY_UPDATE_DICT.items()), True, True),
            lambda: (list(_TEST_DICTIONARY_UPDATE_DICT.items()), True, False),
            lambda: (_TEST_DICTIONARY_UPDATE_STENODICT, False, True),
            lambda: (_TEST_DICTIONARY_UPDATE_STENODICT, False, False),
        )
    )
    def test_update(self, update_from, use_iter, start_empty):
        """
        Check `update` does the right thing, including consuming iterators once.
        """
        d = self.DICT_CLASS()
        if not start_empty:
            d.update(
                {
                    ("SPH*G",): "not something",
                    ("STHEUPBG",): "something",
                    ("EF", "REU", "TH*EUPBG"): "everything",
                }
            )
            assert d[("STHEUPBG",)] == "something"
            assert d[("EF", "REU", "TH*EUPBG")] == "everything"
            if self.DICT_SUPPORT_REVERSE_LOOKUP:
                assert d.reverse_lookup("not something") == {("SPH*G",)}
            else:
                assert d.reverse_lookup("not something") == set()
            if self.DICT_SUPPORT_REVERSE_LOOKUP:
                assert d.casereverse_lookup("not something") == {"not something"}
            else:
                assert d.casereverse_lookup("not something") == set()
            assert d.longest_key == 3
        if use_iter:
            update_from = iter(update_from)
        d.update(update_from)
        assert d[("S-G",)] == "something"
        assert d[("SPH-G",)] == "something"
        assert d[("SPH*G",)] == "Something"
        assert d[("SPH", "THEUPBG")] == "something"
        if not start_empty:
            assert d[("STHEUPBG",)] == "something"
            assert d[("EF", "REU", "TH*EUPBG")] == "everything"
            assert d.reverse_lookup("not something") == set()
            if self.DICT_SUPPORT_REVERSE_LOOKUP:
                assert d.reverse_lookup("something") == {
                    ("STHEUPBG",),
                    ("S-G",),
                    ("SPH-G",),
                    ("SPH", "THEUPBG"),
                }
            else:
                assert d.reverse_lookup("something") == set()
            if self.DICT_SUPPORT_CASEREVERSE_LOOKUP:
                assert d.casereverse_lookup("something") == {"something", "Something"}
            else:
                assert d.casereverse_lookup("something") == set()
            assert d.longest_key == 3
        else:
            if self.DICT_SUPPORT_REVERSE_LOOKUP:
                assert d.reverse_lookup("something") == {
                    ("S-G",),
                    ("SPH-G",),
                    ("SPH", "THEUPBG"),
                }
            else:
                assert d.reverse_lookup("something") == set()
            if self.DICT_SUPPORT_CASEREVERSE_LOOKUP:
                assert d.casereverse_lookup("something") == {"something", "Something"}
            else:
                assert d.casereverse_lookup("something") == set()
            assert d.longest_key == 2

    INVALID_CONTENTS = b"ceci n'est pas un dictionaire"

    def _test_save(self, tmp_path, entries, expected):
        """
        Test `save` implementation.
        """
        dict_entries = self.parse_entries(entries)
        with self.tmp_dict(tmp_path, self.INVALID_CONTENTS) as dict_path:
            st = dict_path.stat()
            old_timestamp = st.st_mtime - 1
            os.utime(str(dict_path), (st.st_atime, old_timestamp))
            # Create...
            d = self.DICT_CLASS.create(str(dict_path))
            # ...must not change the target file...
            assert d.timestamp == 0
            assert dict_path.read_bytes() == self.INVALID_CONTENTS
            # ...even on update...
            d.update(dict_entries)
            assert d.timestamp == 0
            assert dict_path.read_bytes() == self.INVALID_CONTENTS
            # ...until save is called.
            d.save()
            assert d.timestamp > old_timestamp
            if expected is None:
                assert dict_path.read_bytes() != self.INVALID_CONTENTS
            else:
                assert dict_path.read_bytes() == expected
            d = self.DICT_CLASS.load(str(dict_path))
            assert sorted(d.items()) == sorted(dict_entries.items())


def _wrap_method(method):
    @functools.wraps(method)
    def wrapper(*args, **kwargs):
        return method(*args, **kwargs)

    wrapper.__signature__ = inspect.signature(method)
    return wrapper


def dictionary_test(cls):
    """
    Torture tests for dictionary implementations.

    Usage:

    ```python

    @dictionary_test
    class TestMyDictionaryClass:

        # Mandatory: implementation class.
        DICT_CLASS = MyDictionaryClass

        # Mandatory: extension.
        DICT_EXTENSION = 'json'

        # Mandatory: valid sample dictionary contents.
        DICT_SAMPLE = b'{}'

        # Optional: if `True`, will check the implementation class
        # is registered as a valid `plover.dictionary` entrypoint.
        DICT_REGISTERED = True

        # Optional: if `False`, `len`, `__iter__`, and `items`
        # are not supported, and must respectively return:
        # 0 and empty sequences.
        # Note: only supported for read-only implementations,
        # writable implementations must support all sequence
        # methods.
        DICT_SUPPORT_SEQUENCE_METHODS = False

        # Optional: if `False`, then `reverse_lookup` is not
        # supported, and must return an empty set.
        DICT_SUPPORT_REVERSE_LOOKUP = False

        # Optional: if `False`, then `casereverse_lookup` is not
        # supported, and must return an empty set.
        # Note: if supported, then `DICT_SUPPORT_REVERSE_LOOKUP`
        # must be too.
        DICT_SUPPORT_CASEREVERSE_LOOKUP = False

        # Optional: load tests.
        DICT_LOAD_TESTS = (
            lambda: (
                # Dictionary file contents.
                b'''
                ''',
                # Expected entries, in Python-dictionary like format.
                '''
                "TEFT": 'test',
                'TEFT/-G': "testing",
                '''
            ),
        )

        # Optional: save tests.
        # Note: only for writable implementations.
        DICT_SAVE_TESTS = (
            lambda: (
                # Initial entries, in Python-dictionary like format.
                '''
                "TEFT": 'test',
                'TEFT/-G': "testing",
                '''
                # Expected saved dictionary contents, or `None`
                # to skip the byte-for-byte test of the resulting
                # file contents.
                b'''
                ''',
            ),
        )

        # Optional: if implemented, will be called to format
        # the contents before saving to a dictionary file,
        # including for load and save tests.
        @staticmethod
        def make_dict(self, contents):
            return contents

    """

    DICT_SUPPORT_SEQUENCE_METHODS = getattr(cls, "DICT_SUPPORT_SEQUENCE_METHODS", True)
    DICT_SUPPORT_REVERSE_LOOKUP = getattr(cls, "DICT_SUPPORT_REVERSE_LOOKUP", True)
    DICT_SUPPORT_CASEREVERSE_LOOKUP = getattr(
        cls, "DICT_SUPPORT_CASEREVERSE_LOOKUP", DICT_SUPPORT_REVERSE_LOOKUP
    )
    assert DICT_SUPPORT_REVERSE_LOOKUP or not DICT_SUPPORT_CASEREVERSE_LOOKUP

    base_classes = [cls, _DictionaryTests]
    if cls.DICT_CLASS.readonly:
        base_classes.append(_ReadOnlyDictionaryTests)
    else:
        base_classes.append(_WritableDictionaryTests)

    class_dict = {
        "DICT_SUPPORT_SEQUENCE_METHODS": DICT_SUPPORT_SEQUENCE_METHODS,
        "DICT_SUPPORT_REVERSE_LOOKUP": DICT_SUPPORT_REVERSE_LOOKUP,
        "DICT_SUPPORT_CASEREVERSE_LOOKUP": DICT_SUPPORT_CASEREVERSE_LOOKUP,
    }

    if getattr(cls, "DICT_REGISTERED", False):
        class_dict["test_entrypoint"] = _wrap_method(_DictionaryTests._test_entrypoint)

    if hasattr(cls, "DICT_LOAD_TESTS"):
        class_dict["test_load"] = parametrize(cls.DICT_LOAD_TESTS, arity=2)(
            _wrap_method(_DictionaryTests._test_load)
        )

    if hasattr(cls, "DICT_SAVE_TESTS"):
        assert not cls.DICT_CLASS.readonly
        class_dict["test_save"] = parametrize(cls.DICT_SAVE_TESTS, arity=2)(
            _wrap_method(_WritableDictionaryTests._test_save)
        )

    return type(cls.__name__, tuple(base_classes), class_dict)
