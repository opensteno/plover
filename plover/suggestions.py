import collections

from plover.steno import sort_steno_strokes

Suggestion = collections.namedtuple("Suggestion", "text steno_list")


class Suggestions:
    def __init__(self, dictionary):
        self.dictionary = dictionary

    def find(self, translation):
        suggestions = []

        mods = [
            "%s",  # Same
            "{^%s}",  # Prefix
            "{^}%s",
            "{^%s^}",  # Infix
            "{^}%s{^}",
            "{%s^}",  # Suffix
            "%s{^}",
            "{&%s}",  # Fingerspell
            "{#%s}",  # Command
        ]

        possible_translations = {translation}

        # Only strip spaces, so patterns with \n or \t are correctly handled.
        stripped_translation = translation.strip(" ")
        if stripped_translation and stripped_translation != translation:
            possible_translations.add(stripped_translation)

        lowercase_translation = translation.lower()
        if lowercase_translation != translation:
            possible_translations.add(lowercase_translation)

        similar_words = self.dictionary.casereverse_lookup(translation.lower())
        if similar_words:
            possible_translations |= set(similar_words)

        for t in possible_translations:
            for modded_translation in [mod % t for mod in mods]:
                strokes_list = self.dictionary.reverse_lookup(modded_translation)
                if not strokes_list:
                    continue
                strokes_list = sort_steno_strokes(strokes_list)
                suggestion = Suggestion(modded_translation, strokes_list)
                suggestions.append(suggestion)

        return suggestions
