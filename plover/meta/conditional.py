import re

from plover.formatting import _LookAheadAction

IF_NEXT_META_RX = re.compile(r"((?:[^\\/]|\\\\|\\/)*)/?")
IF_NEXT_ESCAPE_RX = re.compile(r"\\([\\/])")


def meta_if_next_matches(ctx, meta):
    pattern, result1, result2 = [
        IF_NEXT_ESCAPE_RX.sub(r"\1", s)
        for s in filter(None, IF_NEXT_META_RX.split(meta, 2))
    ]
    action_list = []
    for alternative in result1, result2:
        action = ctx.new_action()
        action.text = alternative
        action_list.append(action)
    return _LookAheadAction(pattern, *action_list)
