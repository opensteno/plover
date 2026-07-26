from plover.oslayer.config import PLATFORM
from plover.translation import Translation

if PLATFORM == "mac":
    BACK_STRING = "{#Alt_L(BackSpace)}{^}"
else:
    BACK_STRING = "{#Control_L(BackSpace)}{^}"


def undo(translator, stroke, cmdline):
    assert not cmdline
    for t in reversed(translator.get_state().translations):
        translator.untranslate_translation(t)
        if t.has_undo():
            return
    # There is no more buffer to delete from -- remove undo and add a
    # stroke that removes last word on the user's OS, but don't add it
    # to the state history.
    translator.flush([Translation([stroke], BACK_STRING)])
