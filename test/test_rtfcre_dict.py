# Copyright (c) 2013 Hesky Fisher
# See LICENSE.txt for details.

import textwrap

import pytest

from plover import __version__ as plover_version
from plover.dictionary.rtfcre_dict import RtfDictionary, TranslationFormatter
from plover.dictionary.rtfcre_parse import BadRtfError
from plover_build_utils.testing import dictionary_test, parametrize


@parametrize(
    (
        lambda: ("", ""),
        # Affix handling.
        lambda: ("{^}", r"{\cxds}"),
        lambda: ("{^^}", r"{\cxds}"),
        lambda: ("{^in^}", r"{\cxds in\cxds}"),
        lambda: ("{pre^}", r"{pre\cxds}"),
        lambda: ("{pre^} ", r"{pre\cxds}"),
        lambda: ("{pre^}  ", r"{pre\cxds}"),
        lambda: ("{ pre ^}  ", r"{ pre \cxds}"),
        lambda: ("{^post}", r"{\cxds post}"),
        lambda: (" {^post}", r"{\cxds post}"),
        lambda: ("  {^post}", r"{\cxds post}"),
        lambda: ("{^ post }  ", r"{\cxds  post }"),
        # Escaping special characters.
        lambda: (r"\{", r"\\\{"),
        lambda: (r"\}", r"\\\}"),
        # Hard space.
        lambda: ("{^ ^}", r"\~"),
        # Non-breaking hyphen.
        lambda: ("{^-^}", r"\_"),
        # Handling newlines.
        lambda: ("test\nsomething", r"test\line something"),
        lambda: ("test\n\nsomething", r"test\par something"),
        lambda: ("test\\nsomething", r"test\\nsomething"),
        # Handling tabs.
        lambda: ("test\tsomething", r"test\tab something"),
        lambda: ("test\\tsomething", r"test\\tsomething"),
        # Force Cap.
        lambda: (r"Mr.{-|}", r"Mr.\cxfc "),
        # Force Lower Case.
        lambda: (r"{>}lol", r"\cxfl lol"),
        # Infix with force cap.
        lambda: ("{^\n^}{-|}", r"{\cxds \line \cxds}\cxfc "),
        lambda: ("{^\n\n^}{-|}", r"{\cxds \par \cxds}\cxfc "),
        # Plover custom formatting:
        # - meta: command
        lambda: ("{PLOVER:TOGGLE}", r"{\*\cxplovermeta PLOVER:TOGGLE}"),
        # - meta: key combo
        lambda: ("{#Return}", r"{\*\cxplovermeta #Return}"),
        # - meta: other
        lambda: (
            "{:retro_case:cap_first_word}",
            r"{\*\cxplovermeta :retro_case:cap_first_word}",
        ),
        # - macro
        lambda: ("{*}", r"{\*\cxplovermacro retrospective_toggle_asterisk}"),
        lambda: ("{*!}", r"{\*\cxplovermacro retrospective_delete_space}"),
        lambda: ("{*?}", r"{\*\cxplovermacro retrospective_insert_space}"),
        lambda: ("{*+}", r"{\*\cxplovermacro repeat_last_stroke}"),
        lambda: (
            "=retrospective_delete_space",
            r"{\*\cxplovermacro retrospective_delete_space}",
        ),
        lambda: ("=macro:with_arg", r"{\*\cxplovermacro macro:with_arg}"),
        lambda: ("=macro:", r"{\*\cxplovermacro macro:}"),
        lambda: ("=undo", r"\cxdstroke"),
        # - not macros
        lambda: ("==", "=="),
        lambda: ("=test()", "=test()"),
        lambda: (
            "=macro{<-ceci n'est pas une macro}",
            r"=macro{\*\cxplovermeta <-ceci n'est pas une macro}",
        ),
        lambda: ("{*}something", r"{\*\cxplovermeta *}something"),
        # Characters outside code page 1252 are escaped as UTF-16 code units.
        lambda: ("ph\u1edf", r"ph{\uc0\u7903 }"),
        lambda: ("\uc18d", r"{\uc0\u49549 }"),
        lambda: ("\U0001f60a", r"{\uc0\u55357 \u56842 }"),
    )
)
def test_format_translation(before, expected):
    result = TranslationFormatter().format(before)
    assert result == expected


def rtf_load_test(*spec, xfail=False):
    assert 1 <= len(spec) <= 2
    if len(spec) == 2:
        # Conversion test.
        rtf_entries = rf"{{\*\cxs S}}{spec[0]}"
        dict_entries = f'"S": {spec[1]!r}'
    else:
        spec = textwrap.dedent(spec[0]).lstrip()
        if not spec:
            rtf_entries, dict_entries = "", ""
        else:
            rtf_entries, dict_entries = tuple(spec.rsplit("\n\n", 1))
    kwargs = {"marks": pytest.mark.xfail} if xfail else {}
    return pytest.param(rtf_entries, dict_entries, **kwargs)


RTF_LOAD_TESTS = (
    # Empty dictionary.
    lambda: rtf_load_test(
        """



        """
    ),
    # Only one translation.
    lambda: rtf_load_test(
        r"""
        {\*\cxs SP}translation

        'SP': 'translation',
        """
    ),
    # One translation on multiple lines.
    lambda: rtf_load_test(
        """
        {\\*\\cxs SP}\r\ntranslation

        'SP': 'translation'
        """
    ),
    # Steno and translation on multiple lines.
    lambda: rtf_load_test(
        """
        {\\*\\cxs PHA*-EU/SKWRAO-UPB/SKWR-UL/A-UGT/S-EPT/O-BGT/TPHO*-EF/STK-EPL/SKWRA-PB/TP-EB\r\n
        /PHA-R/A-EUP}May, June, July, August, September, October, November, December, January,\r\n
         February, March, April

        ('PHA*-EU/SKWRAO-UPB/SKWR-UL/A-UGT/'
         'S-EPT/O-BGT/TPHO*-EF/STK-EPL/'
         'SKWRA-PB/TP-EB/PHA-R/A-EUP'): (
         'May, June, July, August, September, '
         'October, November, December, January, '
         'February, March, April')
        """
    ),
    # Multiple translations no newlines.
    lambda: rtf_load_test(
        r"""
        {\*\cxs SP}translation{\*\cxs S}translation2

        'SP': 'translation',
        'S': 'translation2',
        """
    ),
    # Multiple translations on separate lines.
    lambda: rtf_load_test(
        """
        {\\*\\cxs SP}translation\r\n{\\*\\cxs S}translation2

        'SP': 'translation',
        'S': 'translation2',
        """
    ),
    lambda: rtf_load_test(
        """
        {\\*\\cxs SP}translation\n{\\*\\cxs S}translation2

        'SP': 'translation',
        'S': 'translation2',
        """
    ),
    # Group start split on 2 lines.
    lambda: rtf_load_test(
        r"""
        {\*\cxs TEFT}{
        \*\ignored I'm invisible}

        'TEFT': '',
        """
    ),
    # Mapping to empty string at end.
    lambda: rtf_load_test(
        r"""
        {\*\cxs TEFT}

        'TEFT': '',
        """
    ),
    # Escaped \r\n handled.
    lambda: rtf_load_test(
        """
        {\\*\\cxs SP}trans\\\r\n

        'SP': 'trans{^\\n\\n^}',
        """
    ),
    # Escaped \r\n handled in mid translation.
    lambda: rtf_load_test(
        """
        {\\*\\cxs SP}trans\\\r\nlation

        'SP': 'trans\\n\\nlation',
        """
    ),
    # Whitespace is preserved in various situations.
    lambda: rtf_load_test(
        r"""
        {\*\cxs S}t  

        'S': 't{^  ^}',
        """
    ),
    lambda: rtf_load_test(
        r"""
        {\*\cxs S}  t

        'S': '{^  ^}t',
        """
    ),
    lambda: rtf_load_test(
        r"""
        {\*\cxs S}t   {\*\cxs T}t    

        'S': 't{^   ^}',
        'T': 't{^    ^}',
        """
    ),
    lambda: rtf_load_test(
        """
        {\\*\\cxs S}t   \r\n{\\*\\cxs T}t    

        'S': 't{^   ^}',
        'T': 't{^    ^}',
        """
    ),
    lambda: rtf_load_test(
        """
        {\\*\\cxs S}t  \r\n{\\*\\cxs T} t \r\n

        'S': 't{^  ^}',
        'T': ' t ',
        """
    ),
    # Translations are ignored if converter returns None
    lambda: rtf_load_test(
        r"""
        {\*\cxs S}return_none

        'S': 'return_none',
        """
    ),
    lambda: rtf_load_test(
        r"""
        {\*\cxs T}t t t  

        'T': 't t t{^  ^}',
        """
    ),
    # Conflicts result on only the last one kept.
    lambda: rtf_load_test(
        r"""
        {\*\cxs T}t
        {\*\cxs T}g

        'T': 'g',
        """
    ),
    lambda: rtf_load_test(
        r"""
        {\*\cxs T}t
        {\*\cxs T}return_none

        'T': 'return_none',
        """
    ),
    # Translation conversion tests.
    # Void...
    lambda: rtf_load_test("", ""),
    # Escaped characters.
    lambda: rtf_load_test(r"\-", "-"),
    lambda: rtf_load_test(r"\\ ", "\\ "),
    lambda: rtf_load_test(r"\\", "\\"),
    lambda: rtf_load_test(r"\{", "{"),
    lambda: rtf_load_test(r"\}", "}"),
    # Hard space.
    lambda: rtf_load_test(r"\~", "{^ ^}"),
    # Non-breaking hyphen.
    lambda: rtf_load_test(r"\_", "{^-^}"),
    # Escaped newline.
    lambda: rtf_load_test("\\\r\n", "{^\n\n^}"),
    # Newline / tabs control words.
    lambda: rtf_load_test(r"test:\line something", "test:\nsomething"),
    lambda: rtf_load_test(r"\line", "\n"),
    lambda: rtf_load_test(r"\tab", "\t"),
    lambda: rtf_load_test(r"{\line at group start}", "\nat group start"),
    lambda: rtf_load_test("test text", "test text"),
    lambda: rtf_load_test("test  text", "test  text"),
    # Delete Spaces.
    lambda: rtf_load_test(r"\cxds", "{^}"),
    lambda: rtf_load_test(r"{\cxds}", "{^}"),
    lambda: rtf_load_test(r"pre\cxds ", "{pre^}"),
    lambda: rtf_load_test(r"{pre\cxds}", "{pre^}"),
    lambda: rtf_load_test(r"pre\cxds  ", "{pre^} "),
    lambda: rtf_load_test(r"pre\cxds", "{pre^}"),
    lambda: rtf_load_test(r"{pre\cxds  }", "{pre^} "),
    lambda: rtf_load_test(r"\cxds post", "{^post}"),
    lambda: rtf_load_test(r"{\cxds post}", "{^post}"),
    lambda: rtf_load_test(r"\cxds in\cxds", "{^in^}"),
    lambda: rtf_load_test(r"\cxds in\cxds ", "{^in^}"),
    lambda: rtf_load_test(r"{\cxds in\cxds}", "{^in^}"),
    # Force Cap.
    lambda: rtf_load_test(r"\cxfc", "{-|}"),
    # Force Lower Case.
    lambda: rtf_load_test(r"\cxfl", "{>}"),
    lambda: rtf_load_test(r"pre\cxfl", "pre{>}"),
    # New paragraph.
    lambda: rtf_load_test(r"\par", "{^\n\n^}"),
    lambda: rtf_load_test(r"{\par test}", "{^\n\n^}test"),
    # Stenovations extensions...
    lambda: rtf_load_test(r"{\*\cxsvatdictflags N}", "{-|}"),
    lambda: rtf_load_test(r"{\*\cxsvatdictflags LN1}", "{-|}"),
    # Styles.
    # Continuation styles are indented.
    lambda: rtf_load_test(r"\par\s4", "{^\n\n    ^}"),
    # caseCATalyst declares new styles without a preceding \par,
    # so we treat it as an implicit par.
    lambda: rtf_load_test(r"\s1", "{^\n\n^}"),
    # But if the \par is present we don't treat \s as an implicit par.
    lambda: rtf_load_test(r"\par\s1", "{^\n\n^}"),
    # caseCATalyst punctuation.
    lambda: rtf_load_test(r".", "{.}"),
    lambda: rtf_load_test(r". ", "{.} "),
    lambda: rtf_load_test(r" . ", " . "),
    # Automatic Text.
    lambda: rtf_load_test(r"{\cxa Q.}.", "Q.."),
    # Don't mess with period that is part of a word.
    lambda: rtf_load_test(r"Mr.", "Mr."),
    lambda: rtf_load_test(r".attribute", ".attribute"),
    # Stitching.
    lambda: rtf_load_test(r"{\cxstit contents}", "contents"),
    # Fingerspelling.
    lambda: rtf_load_test(r"{\cxfing c}", "{&c}"),
    lambda: rtf_load_test(r"\cxfing Z.", "{&Z.}"),
    # Punctuation.
    lambda: rtf_load_test(r"{\cxp.}", "{.}"),
    lambda: rtf_load_test(r"{\cxp .}", "{.}"),
    lambda: rtf_load_test(r"{\cxp . }", "{.}"),
    lambda: rtf_load_test(r"{\cxp .  }", "{.}"),
    lambda: rtf_load_test(r"{\cxp !}", "{!}"),
    lambda: rtf_load_test(r"{\cxp ?}", "{?}"),
    lambda: rtf_load_test(r"{\cxp ,}", "{,}"),
    lambda: rtf_load_test(r"{\cxp ;}", "{;}"),
    lambda: rtf_load_test(r"{\cxp :}", "{:}"),
    lambda: rtf_load_test("{\\cxp '}", "{^'}"),
    lambda: rtf_load_test("{\\cxp -}", "{^-^}"),
    lambda: rtf_load_test("{\\cxp /}", "{^/^}"),
    # Why not '{^...^}'?
    lambda: rtf_load_test("{\\cxp...  }", "{^...  ^}"),
    # Why not '{^")^}'?
    lambda: rtf_load_test('{\\cxp ") }', '{^") ^}'),
    # Unsupported, non-ignored group.
    lambda: rtf_load_test(r"{\nonexistent }", ""),
    lambda: rtf_load_test(r"{\nonexistent contents}", "contents"),
    lambda: rtf_load_test(r"{\nonexistent cont\_ents}", "cont{^-^}ents"),
    lambda: rtf_load_test(r"{\nonexistent {\cxp .}}", "{.}"),
    # Unsupported, ignored group.
    lambda: rtf_load_test(r"{\*\nonexistent }", ""),
    lambda: rtf_load_test(r"{\*\nonexistent contents}", ""),
    lambda: rtf_load_test(r"{\*\nonexistent {\cxp .}}", ""),
    lambda: rtf_load_test(r"be\cxds{\*\cxsvatdictentrydate\yr2006\mo5\dy10}", "{be^}"),
    # Unresolved conflicts.
    lambda: rtf_load_test(r"{\cxconf [{\cxc abc}]}", "[abc]"),
    lambda: rtf_load_test(r"{\cxconf [{\cxc abc}|{\cxc def}]}", "[abc|def]"),
    lambda: rtf_load_test(
        r"{\cxconf [{\cxc abc}|{\cxc def}|{\cxc ghi}]}", "[abc|def|ghi]"
    ),
    lambda: rtf_load_test(
        r"{\cxconf [{\cxc abc}|{\cxc {\cxp... }}]}", "[abc|{^... ^}]"
    ),
    lambda: rtf_load_test(
        r"{\cxconf [{\cxc their}|{\cxc there}|{\cxc they're}]}", "[their|there|they're]"
    ),
    lambda: rtf_load_test(
        r"{\cxconf [{\cxc \par\s4}|{\cxc paragraph}]}", "[\n\n    |paragraph]"
    ),
    # Resolved conflicts.
    lambda: rtf_load_test(
        r"{\cxconf {\cxc their}{\*\deleted {\cxc there}{\cxc they're}}}", "their"
    ),
    lambda: rtf_load_test(
        r"{\cxconf {\*\deleted {\cxc their}}{\cxc there}{\*\deleted {\cxc they're}}}",
        "there",
    ),
    lambda: rtf_load_test(
        r"{\cxconf {\cxc \par\s4}{\*\deleted {\cxc paragraph}}}", "{^\n\n    ^}"
    ),
    lambda: rtf_load_test(
        r"{\cxconf {\*\deleted {\cxc \par\s4}}{\cxc paragraph}}", "paragraph"
    ),
    # Plover custom formatting:
    # - meta: command
    lambda: rtf_load_test(r"{\*\cxplovermeta plover:focus}", "{plover:focus}"),
    # - meta: key combo
    lambda: rtf_load_test(r"{\*\cxplovermeta #Alt_L(Tab Tab)}", "{#Alt_L(Tab Tab)}"),
    # - meta: other
    lambda: rtf_load_test(
        r"{\*\cxplovermeta :retro_currency:$c}", "{:retro_currency:$c}"
    ),
    # - macro
    lambda: rtf_load_test(
        r"{\*\cxplovermacro retrospective_delete_space}", "=retrospective_delete_space"
    ),
    lambda: rtf_load_test(r"\cxdstroke", "=undo"),
    # Unrecoverable content.
    # Bad header.
    lambda: (rb" {  \rtf1 test }", BadRtfError),
    lambda: (rb"\rtf1 test }", BadRtfError),
    lambda: (rb"{\rtf500 ... }", BadRtfError),
    # Recoverable content.
    # Starting new mapping in the middle of previous one.
    lambda: rtf_load_test(
        r"""
        {\*\cxs PWRA*-BGT}{\cxconf [{\cxds arg{\cxc\cxds{\*\cxsvatdictentrydate\yr2016\mo8\da12}
        {\*\cxs #25-UBG}{\cxconf [{\cxc  the talk}|{\cxc\cxsvatds , 1946,}]}{\*\cxsvatdictentrydate
        \yr2016\mo7\da14}
        {\*\cxs #250-UDZ}{\cxconf [{\cxc $25,000}|{\cxc the attitudes}]}{\*\cxsvatdictentrydate
        \yr2016\mo6\da29}

        'PWRA*BGT': '[{^arg}{^}',
        '25UBG': '[ the talk|, 1946,]',
        '250UDZ': '[$25,000|the attitudes]',
        """
    ),
    # Unescaped group end in the middle of a mapping.
    lambda: rtf_load_test(
        r"""
        {\*\cxs SPWHRA*-RB}\cxds \\\cxds{\*\cxsvatdictentrydate\yr2016\mo5\da20}
        {\*\cxs PWRA*-BGTD}\cxds}]}{\*\cxsvatdictentrydate\yr2016\mo8\da12}
        {\*\cxs SPA*-EUS}\cxds ^\cxds{\*\cxsvatdictentrydate\yr2016\mo8\da22}

        'SPWHRA*RB': '{^}\\{^}',
        'PWRA*BGTD' : '{^}]',
        'SPA*EUS' : '{^^^}',
        """
    ),
    # Fingerspelling without content.
    lambda: rtf_load_test(r"\cxfing", ""),
    lambda: (
        rb"{\rtf1\ansi{\*\cxs TEFT}\cxfing",
        """
        'TEFT': ''
        """,
    ),
    # RTF/CRE spec allow the number key letter anywhere...
    lambda: rtf_load_test(
        r"""
        {\*\cxs 2#}2

        '2': '2',
        """
    ),
    # Unicode escapes, including surrogate pairs.
    lambda: rtf_load_test(
        r"""
        {\*\cxs TPA*}ph{\uc0\u7903 }

        'TPA*': 'ph\u1edf',
        """
    ),
    lambda: rtf_load_test(
        r"""
        {\*\cxs SPHAOEUL}{\uc0\u55357 \u56842 }

        'SPHAOEUL': '\U0001f60a',
        """
    ),
    # Negative values, as allowed by the RTF spec.
    lambda: rtf_load_test(
        r"""
        {\*\cxs KPWHA}{\uc0\u-15987 }

        'KPWHA': '\uc18d',
        """
    ),
)


def rtf_save_test(dict_entries, rtf_entries):
    rtf_entries = b"\r\n".join(
        (
            (
                rb"{\rtf1\ansi{\*\cxrev100}\cxdict"
                rb"{\*\cxsystem Plover %s}"
                rb"{\stylesheet{\s0 Normal;}}"
            )
            % plover_version.encode(),
        )
        + rtf_entries
        + (b"}", b"")
    )
    return dict_entries, rtf_entries


RTF_SAVE_TESTS = (
    lambda: rtf_save_test(
        """
        'TEFT': 'test',
        'TEFT/-G': 'testing',
        """,
        (rb"{\*\cxs TEFT}test", rb"{\*\cxs TEFT/-G}testing"),
    ),
    lambda: rtf_save_test(
        """
        'S/T': '{pre^}',
        """,
        (rb"{\*\cxs S/T}{pre\cxds}",),
    ),
    lambda: rtf_save_test(
        r"""
        "PWR-S": "\\{",
        """,
        (rb"{\*\cxs PWR-S}\\\{",),
    ),
    lambda: rtf_save_test(
        r"""
        "TEFT": "test\nsomething",
        """,
        (rb"{\*\cxs TEFT}test\line something",),
    ),
    lambda: rtf_save_test(
        r"""
        "TEFT": "test\\nsomething",
        """,
        (rb"{\*\cxs TEFT}test\\nsomething",),
    ),
    lambda: rtf_save_test(
        """
        "PHROLG": "{PLOVER:TOGGLE}",
        """,
        (rb"{\*\cxs PHROLG}{\*\cxplovermeta PLOVER:TOGGLE}",),
    ),
    # Characters outside code page 1252 must not break saving.
    lambda: rtf_save_test(
        """
        "TPA*": "ph\u1edf",
        "SPHAOEUL": "\U0001f60a",
        """,
        (
            rb"{\*\cxs TPA*}ph{\uc0\u7903 }",
            rb"{\*\cxs SPHAOEUL}{\uc0\u55357 \u56842 }",
        ),
    ),
)


@dictionary_test
class TestRtfDictionary:
    DICT_CLASS = RtfDictionary
    DICT_EXTENSION = "rtf"
    DICT_REGISTERED = True
    DICT_LOAD_TESTS = RTF_LOAD_TESTS
    DICT_SAVE_TESTS = RTF_SAVE_TESTS
    DICT_SAMPLE = ""

    @staticmethod
    def make_dict(contents):
        if isinstance(contents, bytes):
            return contents
        rtf_styles = {
            0: "Normal",
            1: "Question",
            2: "Answer",
            3: "Colloquy",
            4: "Continuation Q",
            5: "Continuation A",
            6: "Continuation Col",
            7: "Paren",
            8: "Centered",
        }
        rtf = "\r\n".join(
            [r"{\rtf1\ansi\cxdict{\*\cxrev100}{\*\cxsystem Fake Software}"]
            + [r"{\stylesheet"]
            + [rf"{{\s{k} {v};}}" for k, v in rtf_styles.items()]
            + ["}", contents, "}", ""]
        )
        return rtf.encode("cp1252")
