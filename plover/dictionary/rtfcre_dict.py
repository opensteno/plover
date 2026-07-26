# Copyright (c) 2013 Hesky Fisher
# See LICENSE.txt for details.
#
# TODO: Convert non-ascii characters to UTF8
# TODO: What does ^ mean in Eclipse?
# TODO: What does #N mean in Eclipse?
# TODO: convert supported commands from Eclipse

"""Parsing an RTF/CRE dictionary.

RTF/CRE spec:
https://web.archive.org/web/20201017075356/http://www.legalxml.org/workgroups/substantive/transcripts/cre-spec.htm

"""

import re
import string

from plover import __version__ as plover_version
from plover.dictionary.helpers import StenoNormalizer
from plover.formatting import ATOM_RE
from plover.steno_dictionary import StenoDictionary

from .rtfcre_parse import parse_rtfcre

HEADER = (
    r"{\rtf1\ansi{\*\cxrev100}"
    rf"\cxdict{{\*\cxsystem Plover {plover_version}}}"
    r"{\stylesheet{\s0 Normal;}}"
)


def escape_unicode(text):
    """Escape characters that code page 1252 cannot represent.

    RTF encodes such characters with the `\\uN` control word, using UTF-16
    code units, so characters outside the BMP are written as a surrogate
    pair. The escapes are wrapped in a group setting `\\uc0` so readers do
    not expect an ANSI fallback character.
    """
    parts = []
    for char in text:
        try:
            char.encode("cp1252")
        except UnicodeEncodeError:
            codepoint = ord(char)
            if codepoint > 0xFFFF:
                codepoint -= 0x10000
                units = (0xD800 + (codepoint >> 10), 0xDC00 + (codepoint & 0x3FF))
            else:
                units = (codepoint,)
            escapes = "".join(rf"\u{unit} " for unit in units)
            char = rf"{{\uc0{escapes}}}"
        parts.append(char)
    return "".join(parts)


class RegexFormatter:
    def __init__(self, spec_list, escape_fn):
        self._escape_fn = escape_fn
        self._format_for_lastindex = [None]
        pattern_list = []
        for pattern, replacement in spec_list:
            num_groups = len(self._format_for_lastindex)
            pattern_groups = re.compile(pattern).groups
            if pattern_groups:
                needed = []
                for token in string.Formatter().parse(replacement):
                    field_name = token[1]
                    if not field_name:
                        continue
                    group = int(field_name)
                    assert 0 <= group <= pattern_groups
                    needed.append(group + num_groups)
            else:
                pattern = "(" + pattern + ")"
                pattern_groups = 1
                needed = []
            for n in range(pattern_groups):
                self._format_for_lastindex.append((needed, replacement))
            pattern_list.append(pattern)
        self._format_rx = re.compile("|".join(pattern_list))

    def format(self, s):
        m = self._format_rx.fullmatch(s)
        if m is None:
            return None
        needed, replacement = self._format_for_lastindex[m.lastindex]
        return replacement.format(*(self._escape_fn(m.group(g)) for g in needed))


class TranslationFormatter:
    # fmt: off
    TO_ESCAPE = (
        (r"([\\{}])", r"\\\1"   ),
        (r"\n\n"    , r"\\par " ),
        (r"\n"      , r"\\line "),
        (r"\t"      , r"\\tab " ),
    )
    ATOMS_FORMATTERS = (
        # Note order matters!
        (r"{\.}"                       , r"{{\cxp. }}"                 ),
        (r"{!}"                        , r"{{\cxp! }}"                 ),
        (r"{\?}"                       , r"{{\cxp? }}"                 ),
        (r"{\,}"                       , r"{{\cxp, }}"                 ),
        (r"{:}"                        , r"{{\cxp: }}"                 ),
        (r"{;}"                        , r"{{\cxp; }}"                 ),
        (r"{\^ \^}"                    , r"\~"                         ),
        (r"{\^-\^}"                    , r"\_"                         ),
        (r"{\^\^?}"                    , r"{{\cxds}}"                  ),
        (r"{\^([^^}]*)\^}"             , r"{{\cxds {0}\cxds}}"         ),
        (r"{\^([^^}]*)}"               , r"{{\cxds {0}}}"              ),
        (r"{([^^}]*)\^}"               , r"{{{0}\cxds}}"               ),
        (r"{-\|}"                      , r"\cxfc "                     ),
        (r"{>}"                        , r"\cxfl "                     ),
        (r"{ }"                        , r" "                          ),
        (r"{&([^}]+)}"                 , r"{{\cxfing {0}}}"            ),
        (r"{(.*)}"                     , r"{{\*\cxplovermeta {0}}}"    ),
    )
    TRANSLATIONS_FORMATTERS = (
        (r"{\*}"                       , r"{{\*\cxplovermacro retrospective_toggle_asterisk}}"),
        (r"{\*!}"                      , r"{{\*\cxplovermacro retrospective_delete_space}}"),
        (r"{\*\?}"                     , r"{{\*\cxplovermacro retrospective_insert_space}}"),
        (r"{\*\+}"                     , r"{{\*\cxplovermacro repeat_last_stroke}}"),
        (r"=undo"                      , r"\cxdstroke"                 ),
        (r"=(\w+(?::.*)?)"             , r"{{\*\cxplovermacro {0}}}"   ),
    )
    # fmt: on

    def __init__(self):
        self._to_escape = [
            (re.compile(pattern), replacement)
            for pattern, replacement in self.TO_ESCAPE
        ]
        self._atom_formatter = RegexFormatter(self.ATOMS_FORMATTERS, self.escape)
        self._translation_formatter = RegexFormatter(
            self.TRANSLATIONS_FORMATTERS, self.escape
        )

    def escape(self, text):
        for rx, replacement in self._to_escape:
            text = rx.sub(replacement, text)
        return escape_unicode(text)

    def format(self, translation):
        s = self._translation_formatter.format(translation)
        if s is not None:
            return s
        parts = []
        for atom in ATOM_RE.findall(translation):
            atom = atom.strip()
            if not atom:
                continue
            s = self._atom_formatter.format(atom)
            if s is None:
                s = self.escape(atom)
            parts.append(s)
        return "".join(parts)


class RtfDictionary(StenoDictionary):
    def _load(self, filename):
        with open(filename, "rb") as fp:
            text = fp.read().decode("cp1252")
        with StenoNormalizer(filename) as normalize_steno:
            self.update(parse_rtfcre(text, normalize=normalize_steno))

    def _save(self, filename):
        translation_formatter = TranslationFormatter()
        with open(filename, "w", encoding="cp1252", newline="\r\n") as fp:
            print(HEADER, file=fp)
            for s, t in self.items():
                s = "/".join(s)
                t = translation_formatter.format(t)
                entry = rf"{{\*\cxs {s}}}{t}"
                print(entry, file=fp)
            print("}", file=fp)
