# Copyright (c) 2013 Hesky Fisher
# See LICENSE.txt for details.

"""Unit tests for json.py."""

from plover.dictionary.json_dict import JsonDictionary
from plover_build_utils.testing import dictionary_test


def json_load_test(contents, expected):
    if isinstance(contents, str):
        contents = contents.encode("utf-8")
    return contents, expected


JSON_LOAD_TESTS = (
    lambda: json_load_test('{"S": "a"}', '"S": "a"'),
    # Default encoding is utf-8.
    lambda: json_load_test('{"S": "café"}', '"S": "café"'),
    # But if that fails, the implementation
    # must automatically retry with latin-1.
    lambda: json_load_test('{"S": "café"}'.encode("latin-1"), '"S": "café"'),
    # Invalid JSON.
    lambda: json_load_test('{"foo", "bar",}', ValueError),
    # Invalid JSON.
    lambda: json_load_test("foo", ValueError),
    # Cannot convert to dict.
    lambda: json_load_test('"foo"', ValueError),
    # Ditto.
    lambda: json_load_test("4.2", TypeError),
)


def json_save_test(entries, expected):
    return entries, expected.encode("utf-8")


JSON_SAVE_TESTS = (
    # Simple test.
    lambda: json_save_test(
        """
        'S': 'a',
        """,
        '{\n"S": "a"\n}\n',
    ),
    # Check strokes format: '/' separated.
    lambda: json_save_test(
        """
        'SAPL/-PL': 'sample',
        """,
        '{\n"SAPL/-PL": "sample"\n}\n',
    ),
    # Contents should be saved as UTF-8, no escaping.
    lambda: json_save_test(
        """
        'S': 'café',
        """,
        '{\n"S": "café"\n}\n',
    ),
    # Check escaping of special characters.
    lambda: json_save_test(
        r"""
        'S': '{^"\n\t"^}',
        """,
        '{\n"S": "' + r"{^\"\n\t\"^}" + '"\n}\n',
    ),
    # Keys are sorted on save.
    lambda: json_save_test(
        """
        'T': 'bravo',
        'S': 'alpha',
        'R': 'charlie',
        """,
        '{\n"S": "alpha",\n"T": "bravo",\n"R": "charlie"\n}\n',
    ),
)


@dictionary_test
class TestJsonDictionary:
    DICT_CLASS = JsonDictionary
    DICT_EXTENSION = "json"
    DICT_REGISTERED = True
    DICT_LOAD_TESTS = JSON_LOAD_TESTS
    DICT_SAVE_TESTS = JSON_SAVE_TESTS
    DICT_SAMPLE = b"{}"
