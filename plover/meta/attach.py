from os.path import commonprefix

from plover.formatting import (
    META_ATTACH_FLAG,
    META_CARRY_CAPITALIZATION,
    Case,
    has_word_boundary,
    rightmost_word,
)
from plover.orthography import add_suffix


def meta_attach(ctx, meta):
    action = ctx.new_action()
    begin = meta.startswith(META_ATTACH_FLAG)
    end = meta.endswith(META_ATTACH_FLAG)
    if not (begin or end):
        # If not specified, attach at both ends.
        meta = META_ATTACH_FLAG + meta + META_ATTACH_FLAG
        begin = end = True
    if begin:
        meta = meta[len(META_ATTACH_FLAG) :]
        action.prev_attach = True
    if end:
        meta = meta[: -len(META_ATTACH_FLAG)]
        action.next_attach = True
        action.word_is_finished = False
    last_word = ctx.last_action.word or ""
    if not meta:
        # We use an empty connection to indicate a "break" in the
        # application of orthography rules. This allows the
        # stenographer to tell Plover not to auto-correct a word.
        action.orthography = False
    elif (
        last_word
        and not meta.isspace()
        and ctx.last_action.orthography
        and begin
        and (not end or has_word_boundary(meta))
    ):
        new_word = add_suffix(last_word, meta)
        common_len = len(commonprefix([last_word, new_word]))
        replaced = last_word[common_len:]
        action.prev_replace = ctx.last_text(len(replaced))
        assert replaced.lower() == action.prev_replace.lower()
        last_word = last_word[:common_len]
        meta = new_word[common_len:]
    action.text = meta
    if action.prev_attach:
        action.word = rightmost_word(last_word + meta)
    return action


def meta_carry_capitalize(ctx, meta):
    # Meta format: ^~|content^ (attach flags are optional)
    action = ctx.new_action()
    if ctx.last_action.next_case == Case.CAP_FIRST_WORD:
        action.next_case = Case.CAP_FIRST_WORD
    begin = meta.startswith(META_ATTACH_FLAG)
    if begin:
        meta = meta[len(META_ATTACH_FLAG) :]
        action.prev_attach = True
    meta = meta[len(META_CARRY_CAPITALIZATION) :]
    end = meta.endswith(META_ATTACH_FLAG)
    if end:
        meta = meta[: -len(META_ATTACH_FLAG)]
        action.next_attach = True
        action.word_is_finished = False
    if meta or begin or end:
        action.text = meta
    return action
