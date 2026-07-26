# Copyright (c) 2013 Hesky Fisher
# See LICENSE.txt for details.

import json
from collections import defaultdict

import pytest

from plover_build_utils.testing import steno_to_stroke

DICT_NAMES = ["main.json", "commands.json", "user.json"]
DICT_PATH = "plover/assets/"


def test_no_duplicates_categorized_files():
    d = defaultdict(list)
    for dictionary in DICT_NAMES:
        with open(DICT_PATH + dictionary, encoding="utf-8") as fp:
            pairs = json.load(fp, object_pairs_hook=lambda x: x)
        for key, value in pairs:
            d[key].append((value, dictionary))
    msg_list = []
    has_duplicate = False
    for key, value_list in d.items():
        if len(value_list) > 1:
            has_duplicate = True
            msg_list.append(f"key: {key}\n")
            for value in value_list:
                msg_list.append("{!r} in {}\n".format(*value))
    msg = "\n" + "".join(msg_list)
    assert not has_duplicate, msg


@pytest.mark.parametrize("dictionary", DICT_NAMES)
def test_entries_are_valid(dictionary):
    all_strokes = []
    with open(DICT_PATH + dictionary, encoding="utf-8") as fp:
        for k in json.load(fp):
            all_strokes += k.split("/")
    for s in set(all_strokes):
        steno_to_stroke(s)
