# Copyright (c) 2013 Hesky Fisher
# See LICENSE.txt for details.

"""Parsing a json formatted dictionary."""

try:
    import simplejson as json
except ImportError:
    import json

from plover.dictionary.helpers import StenoNormalizer
from plover.steno import steno_to_sort_key
from plover.steno_dictionary import StenoDictionary


class JsonDictionary(StenoDictionary):
    def _load(self, filename):
        with open(filename, "rb") as fp:
            contents = fp.read()
        for encoding in ("utf-8", "latin-1"):
            try:
                contents = contents.decode(encoding)
            except UnicodeDecodeError:
                continue
            else:
                break
        else:
            raise ValueError(f"'{filename}' encoding could not be determined")
        d = dict(json.loads(contents))
        with StenoNormalizer(filename) as normalize_steno:
            self.update((normalize_steno(x[0]), x[1]) for x in d.items())

    def _save(self, filename):
        mappings = [("/".join(k), v) for k, v in self.items()]
        mappings.sort(key=lambda i: steno_to_sort_key(i[0], strict=False))
        with open(filename, "w", encoding="utf-8", newline="\n") as fp:
            json.dump(
                dict(mappings), fp, ensure_ascii=False, indent=0, separators=(",", ": ")
            )
            fp.write("\n")
