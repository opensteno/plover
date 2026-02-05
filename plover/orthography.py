# Copyright (c) 2010-2011 Joshua Harlan Lifton.
# See LICENSE.txt for details.

"""Functions that implement some English orthographic rules."""

from plover import system


def make_candidates_from_rules(word, suffix, check=lambda x: True):
    candidates = []
    for r in system.ORTHOGRAPHY_RULES:
        m = r[0].match(word + " ^ " + suffix)
        if m:
            expanded = m.expand(r[1])
            if check(expanded):
                candidates.append(expanded)
    return candidates


def _add_suffix(word, suffix):
    def in_dict_f(x):
        return x in system.ORTHOGRAPHY_WORDS

    candidates = []

    alias = system.ORTHOGRAPHY_RULES_ALIASES.get(suffix, None)
    if alias is not None:
        candidates.extend(make_candidates_from_rules(word, alias, in_dict_f))

    # Try a simple join if it is in the dictionary.
    simple = word + suffix
    if in_dict_f(simple):
        candidates.append(simple)

    # Try rules with dict lookup.
    candidates.extend(make_candidates_from_rules(word, suffix, in_dict_f))

    # For all candidates sort by prominence in dictionary and, since sort is
    # stable, also by the order added to candidates list.
    if candidates:
        candidates.sort(key=lambda x: system.ORTHOGRAPHY_WORDS[x])
        return candidates[0]

    # Try rules without dict lookup.
    candidates = make_candidates_from_rules(word, suffix)
    if candidates:
        return candidates[0]

    # If all else fails then just do a simple join.
    return simple


def add_suffix(word, suffix):
    """Add a suffix to a word by applying the rules above

    Arguments:

    word -- A word
    suffix -- The suffix to add

    """
    suffix, sep, rest = suffix.partition(" ")
    expanded = _add_suffix(word, suffix)
    return expanded + sep + rest
