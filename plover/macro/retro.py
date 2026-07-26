from plover import system
from plover.steno import Stroke
from plover.translation import Translation


def toggle_asterisk(translator, stroke, cmdline):
    assert not cmdline
    # Toggle asterisk of previous stroke
    translations = translator.get_state().translations
    if not translations:
        return
    t = translations[-1]
    translator.untranslate_translation(t)
    keys = set(t.strokes[-1].steno_keys)
    if "*" in keys:
        keys.remove("*")
    else:
        keys.add("*")
    translator.translate_stroke(Stroke(keys))


def delete_space(translator, stroke, cmdline):
    assert not cmdline
    # Retrospective delete space
    translations = translator.get_state().translations
    if len(translations) < 2:
        return
    replaced = translations[-2:]
    if replaced[1].is_retrospective_command:
        return
    english = []
    for t in replaced:
        if t.english is not None:
            english.append(t.english)
        elif len(t.rtfcre) == 1 and t.rtfcre[0].isdigit():
            english.append(f"{{&{t.rtfcre[0]}}}")
    if len(english) > 1:
        t = Translation([stroke], "{^~|^}".join(english))
        t.replaced = replaced
        t.is_retrospective_command = True
        translator.translate_translation(t)


def insert_space(translator, stroke, cmdline):
    assert not cmdline
    # Retrospective insert space
    translations = translator.get_state().translations
    if not translations:
        return
    replaced = translations[-1]
    if replaced.is_retrospective_command:
        return
    lookup_stroke = replaced.strokes[-1]
    english = [t.english or "/".join(t.rtfcre) for t in replaced.replaced]
    if english:
        english.append(
            translator.lookup([lookup_stroke], system.SUFFIX_KEYS)
            or lookup_stroke.rtfcre
        )
        t = Translation([stroke], " ".join(english))
        t.replaced = [replaced]
        t.is_retrospective_command = True
        translator.translate_translation(t)
