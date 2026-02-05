# -*- coding: utf-8 -*-

import re


# Mapping of "standard" keynames (derived from X11 keysym names) to Unicode.
# fmt: off
KEYNAME_TO_CHAR = {
    # Generated using:
    #
    # from Xlib import XK
    # from plover.oslayer.linux.keyboardcontrol_x11 import keysym_to_string
    # for kn, ks in sorted({
    #     name[3:].lower(): getattr(XK, name)
    #     for name in sorted(dir(XK))
    #     if name.startswith('XK_')
    # }.items()):
    #     us = keysym_to_string(ks)
    #     if us == kn or not us:
    #         continue
    # print '    %-20r: %8r, # %s' % (kn, us, us)
    "aacute"            :  "\xe1", # á
    "acircumflex"       :  "\xe2", # â
    "acute"             :  "\xb4", # ´
    "adiaeresis"        :  "\xe4", # ä
    "ae"                :  "\xe6", # æ
    "agrave"            :  "\xe0", # à
    "ampersand"         :     "&", # &
    "apostrophe"        :     "'", # '
    "aring"             :  "\xe5", # å
    "asciicircum"       :     "^", # ^
    "asciitilde"        :     "~", # ~
    "asterisk"          :     "*", # *
    "at"                :     "@", # @
    "atilde"            :  "\xe3", # ã
    "backslash"         :    "\\", # \
    "bar"               :     "|", # |
    "braceleft"         :     "{", # {
    "braceright"        :     "}", # }
    "bracketleft"       :     "[", # [
    "bracketright"      :     "]", # ]
    "brokenbar"         :  "\xa6", # ¦
    "ccedilla"          :  "\xe7", # ç
    "cedilla"           :  "\xb8", # ¸
    "cent"              :  "\xa2", # ¢
    "clear"             :  "\x0b", # 
    "colon"             :     ":", # :
    "comma"             :     ",", # ,
    "copyright"         :  "\xa9", # ©
    "currency"          :  "\xa4", # ¤
    "degree"            :  "\xb0", # °
    "diaeresis"         :  "\xa8", # ¨
    "division"          :  "\xf7", # ÷
    "dollar"            :     "$", # $
    "eacute"            :  "\xe9", # é
    "ecircumflex"       :  "\xea", # ê
    "ediaeresis"        :  "\xeb", # ë
    "egrave"            :  "\xe8", # è
    "equal"             :     "=", # =
    "eth"               :  "\xf0", # ð
    "exclam"            :     "!", # !
    "exclamdown"        :  "\xa1", # ¡
    "grave"             :     "`", # `
    "greater"           :     ">", # >
    "guillemotleft"     :  "\xab", # «
    "guillemotright"    :  "\xbb", # »
    "hyphen"            :  "\xad", # ­
    "iacute"            :  "\xed", # í
    "icircumflex"       :  "\xee", # î
    "idiaeresis"        :  "\xef", # ï
    "igrave"            :  "\xec", # ì
    "less"              :     "<", # <
    "macron"            :  "\xaf", # ¯
    "masculine"         :  "\xba", # º
    "minus"             :     "-", # -
    "mu"                :  "\xb5", # µ
    "multiply"          :  "\xd7", # ×
    "nobreakspace"      :  "\xa0", #  
    "notsign"           :  "\xac", # ¬
    "ntilde"            :  "\xf1", # ñ
    "numbersign"        :     "#", # #
    "oacute"            :  "\xf3", # ó
    "ocircumflex"       :  "\xf4", # ô
    "odiaeresis"        :  "\xf6", # ö
    "ograve"            :  "\xf2", # ò
    "onehalf"           :  "\xbd", # ½
    "onequarter"        :  "\xbc", # ¼
    "onesuperior"       :  "\xb9", # ¹
    "ooblique"          :  "\xd8", # Ø
    "ordfeminine"       :  "\xaa", # ª
    "oslash"            :  "\xf8", # ø
    "otilde"            :  "\xf5", # õ
    "paragraph"         :  "\xb6", # ¶
    "parenleft"         :     "(", # (
    "parenright"        :     ")", # )
    "percent"           :     "%", # %
    "period"            :     ".", # .
    "periodcentered"    :  "\xb7", # ·
    "plus"              :     "+", # +
    "plusminus"         :  "\xb1", # ±
    "question"          :     "?", # ?
    "questiondown"      :  "\xbf", # ¿
    "quotedbl"          :     '"', # "
    "quoteleft"         :     "`", # `
    "quoteright"        :     "'", # '
    "registered"        :  "\xae", # ®
    "return"            :    "\r", # 
    "section"           :  "\xa7", # §
    "semicolon"         :     ";", # ;
    "slash"             :     "/", # /
    "space"             :     " ", #  
    "ssharp"            :  "\xdf", # ß
    "sterling"          :  "\xa3", # £
    "tab"               :    "\t", # 	
    "thorn"             :  "\xfe", # þ
    "threequarters"     :  "\xbe", # ¾
    "threesuperior"     :  "\xb3", # ³
    "twosuperior"       :  "\xb2", # ²
    "uacute"            :  "\xfa", # ú
    "ucircumflex"       :  "\xfb", # û
    "udiaeresis"        :  "\xfc", # ü
    "ugrave"            :  "\xf9", # ù
    "underscore"        :     "_", # _
    "yacute"            :  "\xfd", # ý
    "ydiaeresis"        :  "\xff", # ÿ
    "yen"               :  "\xa5", # ¥
}
# fmt: on
for char in "0123456789abcdefghijklmnopqrstuvwxyz":
    KEYNAME_TO_CHAR[char] = char
CHAR_TO_KEYNAME = {char: name for name, char in KEYNAME_TO_CHAR.items()}


_SPLIT_RX = re.compile(r"(\s+|(?:\w+(?:\s*\()?)|.)")


def parse_key_combo(combo_string, key_name_to_key_code=None):
    if key_name_to_key_code is None:

        def key_name_to_key_code(key_name):
            return key_name

    key_events = []
    down_keys = []
    token = None
    count = 0

    def _raise_error(exception, details):
        msg = '%s in "%s"' % (
            details,
            combo_string[:count]
            + "["
            + token
            + "]"
            + combo_string[count + len(token) :],
        )
        raise exception(msg)

    for token in _SPLIT_RX.split(combo_string):
        if not token:
            continue

        if token.isspace():
            pass

        elif re.match(r"\w", token):
            if token.endswith("("):
                key_name = token[:-1].rstrip().lower()
                release = False
            else:
                key_name = token.lower()
                release = True

            key_code = key_name_to_key_code(key_name)
            if key_code is None:
                _raise_error(ValueError, "unknown key")
            elif key_code in down_keys:
                _raise_error(ValueError, 'key "%s" already pressed' % key_name)

            key_events.append((key_code, True))

            if release:
                key_events.append((key_code, False))
            else:
                down_keys.append(key_code)

        elif token == ")":
            if not down_keys:
                _raise_error(SyntaxError, 'unbalanced ")"')
            key_code = down_keys.pop()
            key_events.append((key_code, False))

        else:
            _raise_error(SyntaxError, 'invalid character "%s"' % token)

        count += len(token)

    if down_keys:
        _raise_error(SyntaxError, 'unbalanced "("')

    return key_events


def add_modifiers_aliases(dictionary):
    """Add aliases for common modifiers to a dictionary of key name to key code.

    - add `mod` for `mod_l` aliases for `alt`, `control`, `shift` and `super`
    - add `command` and `windows` aliases for `super`
    - add `option` alias for `alt`
    """
    for name, extra_aliases in (
        ("control", ""),
        ("shift", ""),
        ("super", "command windows"),
        (
            "alt",
            "option",
        ),
    ):
        code = dictionary[name + "_l"]
        dictionary[name] = code
        for alias in extra_aliases.split():
            dictionary[alias] = code
