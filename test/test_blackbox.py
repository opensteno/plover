from typing import ClassVar

import pytest

from plover import system
from plover.registry import Registry
from plover.system import english_stenotype
from plover_build_utils.testing import blackbox_test


@pytest.fixture
def with_melani_system(monkeypatch, request):
    class Melani:
        # fmt: off
        KEYS = (
            "#",
            "S-", "P-", "C-", "T-", "H-", "V-", "R-",
            "I-", "A-",
            "-E", "-O",
            "-c", "-s", "-t", "-h", "-p", "-r",
            "*",
            "-i", "-e", "-a", "-o",
        )
        # fmt: on
        IMPLICIT_HYPHEN_KEYS = KEYS
        SUFFIX_KEYS = ()
        NUMBER_KEY = "#"
        NUMBERS: ClassVar[dict] = {
            "S-": "1-",
            "P-": "2-",
            "T-": "3-",
            "V-": "4-",
            "I-": "5-",
            "-O": "0-",
            "-c": "-6",
            "-t": "-7",
            "-p": "-8",
            "-i": "-9",
        }
        UNDO_STROKE_STENO = "*"
        ORTHOGRAPHY_RULES: ClassVar[list] = []
        ORTHOGRAPHY_RULES_ALIASES: ClassVar[dict] = {}
        ORTHOGRAPHY_WORDLIST = None
        KEYMAPS: ClassVar[dict] = {}
        DICTIONARIES_ROOT = None
        DEFAULT_DICTIONARIES = ()

    registry = Registry()
    registry.register_plugin("system", "English Stenotype", english_stenotype)
    registry.register_plugin("system", "Melani", Melani)
    old_system_name = system.NAME
    with monkeypatch.context() as mp:
        mp.setattr("plover.system.registry", registry)
        yield
    system.setup(old_system_name)


@pytest.fixture
def with_korean_system(monkeypatch, request):
    class KoreanCAS:
        # fmt: off
        KEYS = (
            "1-", "2-", "3-", "4-", "5-",
            "ㅎ-", "ㅁ-", "ㄱ-", "ㅈ-", "ㄴ-",
            "ㄷ-", "ㅇ-", "ㅅ-", "ㅂ-", "ㄹ-",
            "ㅗ-", "ㅏ-", "ㅜ-",
            "-*", "-ㅓ", "-ㅣ",
            "-6", "-7", "-8", "-9", "-0",
            "-ㅎ", "-ㅇ", "-ㄹ", "-ㄱ", "-ㄷ",
            "-ㅂ", "-ㄴ", "-ㅅ", "-ㅈ", "-ㅁ",
        )
        # fmt: on
        IMPLICIT_HYPHEN_KEYS = (
            "ㅗ-",
            "ㅏ-",
            "ㅜ-",
            "-*",
            "-ㅓ",
            "-ㅣ",
        )
        SUFFIX_KEYS = ()
        NUMBER_KEY = None
        NUMBERS: ClassVar[dict] = {}
        UNDO_STROKE_STENO = "-ㅂㄴ"
        ORTHOGRAPHY_RULES: ClassVar[list] = []
        ORTHOGRAPHY_RULES_ALIASES: ClassVar[dict] = {}
        ORTHOGRAPHY_WORDLIST = None
        KEYMAPS: ClassVar[dict] = {}
        DICTIONARIES_ROOT = None
        DEFAULT_DICTIONARIES = ()

    registry = Registry()
    registry.register_plugin("system", "English Stenotype", english_stenotype)
    registry.register_plugin("system", "Korean Modern C", KoreanCAS)
    old_system_name = system.NAME
    with monkeypatch.context() as mp:
        mp.setattr("plover.system.registry", registry)
        yield
    system.setup(old_system_name)


@blackbox_test
class TestsBlackbox:
    def test_translator_state_handling(self):
        # Check if the translator curtailing the list of last translations
        # according to its dictionary longest key does no affect things
        # like the restrospective repeat-last-stroke command.
        r"""
        "TEFT": "test",
        "R*S": "{*+}",

        TEFT/R*S  " test test"
        """

    def test_force_lowercase_title(self):
        r"""
        "T-LT": "{MODE:title}",
        "TEFT": "{>}test",

        T-LT/TEFT  " test"
        """

    def test_bug471(self):
        # Repeat-last-stroke after typing two numbers outputs the numbers
        # reversed for some combos.
        r"""
        "R*S": "{*+}",

        12/R*S  " 1212"
        """

    def test_bug535(self):
        # Currency formatting a number with a decimal fails by not erasing
        # the previous output.
        r"""
        "P-P": "{^.^}",
        "KR*UR": "{*($c)}",

        1/P-P/2/KR*UR  " $1.20"
        """

    def test_bug606(self):
        r"""
        "KWEGS": "question",
        "-S": "{^s}",
        "TP-PL": "{.}",

        :spaces_after
        KWEGS/-S/TP-PL  "questions. "
        """

    def test_bug535_spaces_after(self):
        # Currency formatting a number with a decimal fails by not erasing
        # the previous output.
        r"""
        "P-P": "{^.^}",
        "KR*UR": "{*($c)}",

        :spaces_after
        1/P-P/2/KR*UR  "$1.20 "
        """

    def test_undo_not_defined(self):
        r"""
        'TEFT': 'test',

        TEFT  ' test'
        *     ''
        """

    def test_undo_overriden(self):
        r"""
        'TEFT': 'test',
        '*': 'not undo',

        TEFT  ' test'
        *     ' test not undo'
        """

    def test_undo_macro(self):
        r"""
        'TEFT': 'test',
        'TPH-D': '=undo',

        TEFT   ' test'
        TPH-D  ''
        """

    def test_undo_fingerspelling_1(self):
        r"""
        'T*': '{>}{&t}',
        '*E': '{>}{&e}',
        'S*': '{>}{&s}',
        'T*': '{>}{&t}',

        T*/*E/S*/T*  ' test'
        */*          ' te'
        */*          ''
        """

    def test_undo_fingerspelling_2(self):
        r"""
        'T*': '{>}{&t}',
        '*E': '{>}{&e}',
        'S*': '{>}{&s}',
        'T*': '{>}{&t}',

        :spaces_after
        T*/*E/S*/T*  'test '
        */*          'te '
        */*          ''
        """

    def test_undo_replaced_1(self):
        r"""
        "TEFT": "test",
        "TEFT/TKPWOEFT": "{}",

        TEFT      ' test'
        TKPWOEFT  ''
        *         ' test'
        """

    def test_undo_replaced_2(self):
        r"""
        "HROS": "loss",
        "HRO*S": "lost",
        "*P": "{*}",

        HROS   ' loss'
        *P     ' lost'
        *      ''
        """

    def test_undo_replaced_3(self):
        r"""
        'PER': 'perfect',
        'SWAEUGS': 'situation',
        'PER/SWAEUGS': 'persuasion',
        'SP*': '{*?}',

        PER      ' perfect'
        SWAEUGS  ' persuasion'
        SP*      ' perfect situation'
        *        ' persuasion'
        """

    def test_bug557(self):
        # Using the asterisk key to delete letters in fingerspelled words
        # occasionally causes problems when the space placement is set to
        # "After Output".
        r"""
        "EU": "I",
        "HRAOEUBG": "like",
        "T*": "{>}{&t}",
        "A*": "{>}{&a}",
        "KR*": "{>}{&c}",
        "O*": "{>}{&o}",
        "S*": "{>}{&s}",

        :spaces_after
        EU/HRAOEUBG/T*/A*/KR*/O*/S*/*/*/*  "I like ta "
        """

    def test_bug557_resumed(self):
        # Using the asterisk key to delete letters in fingerspelled words
        # occasionally causes problems when the space placement is set to
        # "After Output".
        r"""
        "EU": "I",
        "HRAOEUBG": "like",
        "T*": "{>}{&t}",
        "A*": "{>}{&a}",
        "KR*": "{>}{&c}",
        "O*": "{>}{&o}",
        "S*": "{>}{&s}",

        :spaces_after
        EU/HRAOEUBG/T*/A*/KR*/O*/S*/*/*/*/*/*/HRAOEUBG  "I like like "
        """

    def test_bug557_capitalized(self):
        # Using the asterisk key to delete letters in fingerspelled words
        # occasionally causes problems when the space placement is set to
        # "After Output".
        r"""
        "EU": "I",
        "HRAOEUBG": "like",
        "T*": "{-|}{&t}",
        "A*": "{-|}{&a}",
        "KR*": "{-|}{&c}",
        "O*": "{-|}{&o}",
        "S*": "{-|}{&s}",

        :spaces_after
        EU/HRAOEUBG/T*/A*/KR*/O*/S*/*/*/*  "I like TA "
        """

    def test_capitalized_fingerspelling_spaces_after(self):
        r"""
        "HRAOEUBG": "like",
        "T*": "{&T}",
        "A*": "{&A}",
        "KR*": "{&C}",
        "O*": "{&O}",
        "S*": "{&S}",

        :spaces_after
        HRAOEUBG/T*/A*/KR*/O*/S*  "like TACOS "
        """

    def test_special_characters(self):
        r"""
        "R-R": "{^}\n{^}",
        "TAB": "\t",

        R-R/TAB  "\n\t"
        """

    def test_automatic_suffix_keys_1(self):
        r"""
        "RAEUS": "race",
        "RAEUZ": "raise",
        "-S": "{^s}",
        "-Z": "{^s}",

        RAEUSZ  " races"
        """

    def test_bug719(self):
        # Glue (&) does not work with "Spaces After".
        r"""
        "P*": "{&P}"

        :spaces_after
        P*/P*/P*/P*/P*/P*  'PPPPPP '
        """

    def test_bug741(self):
        # Uppercase last word also uppercases next word's prefix.
        r"""
        "KPA*TS": "{*<}",
        "TPAO": "foo",
        "KAUPB": "{con^}",

        TPAO/KPA*TS/KAUPB/TPAO  " FOO confoo"
        """

    def test_carry_capitalization_spacing1(self):
        r"""
        'S-P': '{^ ^}',
        'R-R': '{^~|\n^}',

        S-P/R-R  ' \n'
        """

    def test_carry_capitalization_spacing2(self):
        r"""
        'S-P': '{^ ^}',
        'R-R': '{^~|\n^}',

        :spaces_after
        S-P/R-R  ' \n'
        """

    def test_orthography1(self):
        r"""
        'TEFT': 'test',
        '-G': '{^ing}',

        TEFT/-G  ' testing'
        """

    def test_orthography2(self):
        r"""
        'SKEL': 'cancel',
        '-G': '{^ing}',

        SKEL/-G  " canceling"
        """

    def test_orthography3(self):
        r"""
        'PREPB': '{(^}',
        'SKEL': 'cancel',
        '-G': '{^ing}',

        PREPB/SKEL/-G  " (canceling"
        """

    def test_orthography4(self):
        r"""
        'SKEL': '{&c}{&a}{&n}{&c}{&e}{&l}',
        '-G': '{^ing}',

        SKEL/-G  " canceling"
        """

    def test_orthography5(self):
        r"""
        'TPAOEUPL': 'time',
        '-G': '{^ing}',

        TPAOEUPL/-G  ' timing'
        """

    def test_orthography6(self):
        r"""
        'PRE': '{prefix-^}',
        'SKEL': 'cancel',
        '-G': '{^ing}',

        PRE/SKEL/-G  " prefix-canceling"
        """

    def test_orthography7(self):
        r"""
        'PRE': '{prefix^}',
        'SKEL': 'cancel',
        '-G': '{^ing}',

        PRE/SKEL/-G  " prefixcanceling"
        """

    def test_orthography8(self):
        r"""
        'PRE': '{&p}{&r}{&e}{&f}{&i}{&x}',
        "TK-LS": "{^}",
        'SKEL': 'cancel',
        '-G': '{^ing}',

        PRE/TK-LS/SKEL/-G  " prefixcanceling"
        """

    def test_orthography9(self):
        r"""
        'PRE': '{prefix^}',
        'SKEL': '{&c}{&a}{&n}{&c}{&e}{&l}',
        '-G': '{^ing}',

        PRE/SKEL/-G  " prefixcanceling"
        """

    def test_orthography10(self):
        r"""
        'PHO*D': "{MODE:CAMEL}",
        'PRE': '{prefix^}',
        'SKEL': 'cancel',
        '-G': '{^ing}',

        PHO*D/PRE/SKEL/-G  "prefixcanceling"
        """

    def test_orthography11(self):
        r"""
        'PHO*D': "{MODE:SNAKE}",
        'TEFT': 'test',
        'SKEL': 'cancel',
        '-G': '{^ing}',

        PHO*D/TEFT  "_test"
        SKEL/-G     "_test_canceling"
        """

    def test_orthography12(self):
        r"""
        'PHO*D': "{MODE:CAMEL}",
        'TEFT': 'test',
        'SKEL': 'cancel',
        '-G': '{^ing}',

        PHO*D/TEFT  "test"
        SKEL/-G     "testCanceling"
        """

    def test_orthography13(self):
        r"""
        'PHO*D': "{MODE:SNAKE}",
        'PRE': '{prefix^}',
        'TEFT': 'test',
        'SKEL': 'cancel',
        '-G': '{^ing}',

        PHO*D/TEFT  "_test"
        PRE/SKEL/-G     "_test_prefixcanceling"
        """

    def test_orthography14(self):
        r"""
        'PHO*D': "{MODE:CAMEL}",
        'PRE': '{prefix^}',
        'TEFT': 'test',
        'SKEL': 'cancel',
        '-G': '{^ing}',

        PHO*D/TEFT  "test"
        PRE/SKEL/-G     "testPrefixcanceling"
        """

    def test_orthography15(self):
        r"""
        'PHO*D': "{MODE:CAPS}",
        'SKEL': 'cancel',
        '-G': '{^ing}',

        PHO*D/SKEL/-G  " CANCELING"
        """

    def test_orthography16(self):
        r"""
        'SKEL': '{&C}{&A}{&N}{&C}{&E}{&L}',
        '-G': '{^ing}',

        SKEL/-G  " CANCELLing"
        """

    def test_orthography17(self):
        r"""
        'SKEL': 'CANCEL',
        '-G': '{^ing}',

        SKEL/-G  " CANCELLing"
        """

    def test_orthography18(self):
        r"""
        'TPAOEUPL': 'TIME',
        '-G': '{^ing}',

        TPAOEUPL/-G  ' TIMing'
        """

    def test_orthography19(self):
        r"""
        'TPAOEUPL': '{&T}{&I}{&M}{&E}',
        '-G': '{^ing}',

        TPAOEUPL/-G  ' TIMing'
        """

    def test_after_initial_being(self):
        r"""
        '-B': 'be',
        '-B/-G': 'being',

        :spaces_after
        -B/-G  'being '
        """

    def test_after_period(self):
        r"""
        'TEFT': 'test',
        'P-P': '{.}',

        :spaces_after
        TEFT/P-P/TEFT  'test. Test '
        """

    def test_spaces_after1(self):
        r"""
        'TEFT': 'test',
        'TEFTD': 'tested',
        '-G': '{^ing}',
        'P-P': '{.}',

        :spaces_after
        TEFT   'test '
        -G     'testing '
        P-P    'testing. '
        TEFTD  'testing. Tested '
        """

    def test_start_attached1(self):
        r"""
        'TEFT': 'test',

        :start_attached
        TEFT  'test'
        """

    def test_start_attached2(self):
        r"""
        'TEFT': 'test',

        :start_attached
        :spaces_after
        TEFT  'test '
        """

    def test_space_placement_change1(self):
        r"""
        'TEFT': 'test',
        'TEFTD': 'tested',
        'TEFTS': 'tests',

        :spaces_before
        TEFT/TEFTD      ' test tested'
        :spaces_after
        TEFTS/TEFT      ' test tested tests test '
        """

    def test_space_placement_change2(self):
        r"""
        'TEFT': 'test',
        'TEFTD': 'tested',
        'TEFTS': 'tests',

        :spaces_after
        TEFT/TEFTD      'test tested '
        :spaces_before
        TEFTS/TEFT      'test tested tests test'
        """

    def test_undo_after_space_placement_change1(self):
        r"""
        'TEFT': 'test',
        'TEFTD': 'tested',

        :spaces_before
        TEFT/TEFTD      ' test tested'
        :spaces_after
        *               ' test '
        *               ''
        """

    def test_undo_after_space_placement_change2(self):
        r"""
        'TEFT': 'test',
        'TEFTD': 'tested',

        :spaces_after
        TEFT/TEFTD      'test tested '
        :spaces_before
        *               'test'
        *               ''
        """

    def test_undo_after_space_placement_change3(self):
        r"""
        'KPA': '{}{-|}',
        'TEFT': 'test',
        'TEFTD': 'tested',

        :spaces_before
        KPA/TEFT/TEFTD  ' Test tested'
        :spaces_after
        *               ' Test '
        *               ''
        """

    def test_undo_after_space_placement_change4(self):
        r"""
        'KPA': '{}{-|}',
        'TEFT': 'test',
        'TEFTD': 'tested',

        :spaces_after
        KPA/TEFT/TEFTD  ' Test tested '
        :spaces_before
        *               ' Test'
        *               ''
        """

    def test_undo_with_space_placement_changes(self):
        r"""
        'TEFT': 'test',

        TEFT/TEFT/TEFT  ' test test test'
        :spaces_after
        *               ' test test '
        :spaces_before
        *               ' test'
        :spaces_after
        *               ''
        """

    def test_carry_capitalization1(self):
        r"""
        'KA*US': "{~|'^}cause",
        'TEFT': 'test',
        'P-P': '{.}',

        P-P/KA*US/TEFT  ". 'Cause test"
        """

    def test_carry_capitalization2(self):
        r"""
        "KR-GS": "{^~|\"}",

        KR-GS  '"'
        """

    def test_carry_capitalization3(self):
        r"""
        'TP*U': '{<}',
        "TK-LS": "{^}",
        'TEFT': 'test',
        'S-FBGS': '{^suffix}',

        TP*U/TEFT/S-FBGS/TK-LS/S-FBGS  ' TESTSUFFIXSUFFIX'
        """

    def test_carry_capitalization4(self):
        r"""
        'TP*U': '{<}',
        "TK-LS": "{^}",
        'TEFT': 'test',
        "S-P": "{^ ^}"

        TP*U/TEFT/S-P/TEFT  ' TEST test'
        """

    def test_carry_capitalization5(self):
        r"""
        'TP*U': '{<}',
        "TK-LS": "{^}",
        'TEFT': 'test',
        'S-FBGS': '{^suffix}',
        "S-P": "{^ ^}"

        TP*U/TEFT/S-FBGS/S-P/S-FBGS  ' TESTSUFFIX suffix'
        """

    def test_capitalize1(self):
        r"""
        'KPA': '{}{-|}',
        'TEFT': 'test',

        KPA/TEFT  ' Test'
        """

    def test_capitalize2(self):
        r"""
        'KPA': '{}{-|}',
        'TEFT': 'test',

        :start_attached
        KPA/TEFT  ' Test'
        """

    def test_capitalize3(self):
        r"""
        'KPA': '{}{-|}',
        'TEFT': 'test',

        :spaces_after
        KPA/TEFT  ' Test '
        """

    def test_capitalize4(self):
        r"""
        'KPA': '{}{-|}',
        'TEFT': 'test',

        :start_attached
        :spaces_after
        KPA/TEFT  ' Test '
        """

    def test_retro_capitalize1(self):
        r"""
        'KWEUP': 'equip',
        'RUP': '{*-|}',

        KWEUP/RUP  ' Equip'
        """

    def test_retro_capitalize2(self):
        r"""
        'KWEUP': 'equip',
        'RUP': '{*-|}',

        :spaces_after
        KWEUP/RUP  'Equip '
        """

    def test_retro_capitalize3(self):
        r"""
        'TEFT': 'tèśtîñg',
        'RUP': '{*-|}',

        TEFT/RUP  ' Tèśtîñg'
        """

    def test_retro_capitalize4(self):
        r"""
        'PRE': '{pre^}',
        'TPEUBG': 'fix',
        'RUP': '{*-|}',

        PRE/TPEUBG/RUP  ' Prefix'
        """

    def test_retro_capitalize5(self):
        r"""
        'KWEUP': 'equip',
        'RUP': '{:retro_case:cap_first_word}',

        KWEUP/RUP  ' Equip'
        """

    def test_retro_currency1(self):
        r"""
        'TPHAPB': 'notanumber',
        'R-BG': '{*($c)}',

        TPHAPB/R-BG  ' notanumber'
        """

    def test_retro_currency2(self):
        r"""
        'TPHAPB': 'notanumber',
        'R-BG': '{*($c)}',

        :spaces_after
        TPHAPB/R-BG  'notanumber '
        """

    def test_retro_currency3(self):
        r"""
        'R-BG': '{*($c)}',

        0/R-BG  ' $0'
        """

    def test_retro_currency4(self):
        r"""
        'R-BG': '{*($c)}',

        :spaces_after
        0/R-BG  '$0 '
        """

    def test_retro_currency5(self):
        r"""
        'R-BG': '{:retro_currency:$c}',

        0/R-BG  ' $0'
        """

    def test_retro_currency6(self):
        r"""
        'R-BG': '{:retro_currency:$c}',
        'THO*U': '{^},000'

        23/THO*U/R-BG  ' $23,000'
        """

    def test_retro_currency7(self):
        r"""
        'R-BG': '{:retro_currency:$c}',
        'P-P': '{^}.{^}',
        'THO*U': '{^},000'

        23/THO*U/P-P/15/R-BG  ' $23,000.15'
        """

    def test_retro_currency8(self):
        r"""
        'R-BG': '{:retro_currency:$c}',
        'P-P': '{^}.{^}',
        'TPR*UPBT': '{^},500,000'

        4/3/1/TPR*UPBT/P-P/69/R-BG  ' $431,500,000.69'
        """

    def test_retro_upper1(self):
        r"""
        'TEFT': 'test',
        '-G': '{^ing}',
        'PRE': '{pre^}',
        'R*U': '{*<}',

        TEFT/-G/R*U/PRE  " TESTING pre"
        """

    def test_retro_upper2(self):
        r"""
        'TEFT': 'test',
        '-G': '{^ing}',
        'PRE': '{pre^}',
        'R*U': '{*<}',

        TEFT/R*U/-G/PRE  " TESTing pre"
        """

    def test_retro_upper3(self):
        r"""
        'PRE': '{prefix^}',
        'WORD': 'word',
        'R*U': '{*<}',

        PRE/WORD/R*U  " PREFIXWORD"
        """

    def test_retro_upper4(self):
        r"""
        'S-G': 'something',
        'R*U': '{*<}',

        S-G/S-G/R*U/R*U  " something SOMETHING"
        """

    def test_retro_upper5(self):
        r"""
        'TEFT': 'tèśtîñg',
        'RUP': '{*<}',

        TEFT/RUP  ' TÈŚTÎÑG'
        """

    def test_retro_upper6(self):
        r"""
        'ST': 'it is',
        'RUP': '{*<}',

        ST/RUP  " it IS"
        """

    def test_retro_upper7(self):
        r"""
        'TEFT': 'test',
        "W-G": "{^ing with}",
        'RUP': '{*<}',

        TEFT/RUP/W-G  " TESTing with"
        """

    def test_retro_upper8(self):
        r"""
        'TEFT': 'test',
        "W-G": "{^ing with}",
        'RUP': '{*<}',

        TEFT/W-G/RUP  " testing WITH"
        """

    def test_retro_upper9(self):
        r"""
        'TEFT': 'test',
        "W-G": "{^ing with}",
        'RUP': '{*<}',

        TEFT/RUP/W-G/W-G  " TESTing withing with"
        """

    def test_retro_upper10(self):
        r"""
        'TEFT': 'test',
        "W": "with",
        'RUP': '{*<}',

        TEFT/RUP/W/W  " TEST with with"
        """

    def test_retro_upper11(self):
        r"""
        "PREPB": "{~|(^}",
        'TEFT': 'test',
        'RUP': '{*<}',

        PREPB/TEFT/RUP  " (TEST"
        """

    def test_retro_upper12(self):
        r"""
        'PRE': '{pre^}',
        "PREPB": "{~|(^}",
        'TEFT': 'test',
        'RUP': '{*<}',

        PRE/PREPB/TEFT/RUP  " pre(TEST"
        """

    def test_retro_upper13(self):
        r"""
        "PEUD": "pid",
        "TPAOEUL": "file",
        "H*PB": "{^-^}",
        'RUP': '{*<}',

        PEUD/RUP/H*PB/TPAOEUL  ' PID-file'
        """

    def test_retro_upper14(self):
        r"""
        "PEUD": "pid",
        "TPAOEUL": "file",
        "H*PB": "{^-^}",
        'RUP': '{*<}',

        PEUD/H*PB/TPAOEUL/RUP  ' PID-FILE'
        """

    def test_retro_upper15(self):
        r"""
        "OEU": "{^/^}",
        "T*": "{>}{&t}",
        "A*": "{>}{&a}",
        "KR*": "{>}{&c}",
        "O*": "{>}{&o}",
        "S*": "{>}{&s}",
        'RUP': '{*<}',

        T*/A*/OEU/KR*/O*/S*/RUP  ' ta/COS'
        """

    def test_retro_upper16(self):
        r"""
        "S*": "{>}{&s}",
        "T*": "{>}{&t}",
        "O*": "{>}{&o}",
        "STA*R": "{^*^}",
        "*E": "{>}{&e}",
        "*U": "{>}{&u}",
        "P*": "{>}{&p}",
        "PW*": "{>}{&b}",
        'RUP': '{*<}',

        S*/T*/O*/STA*R/*E/*U/P*/PW*/RUP  ' sto*EUPB'
        """

    def test_retro_upper17(self):
        r"""
        "*U": "{>}{&u}",
        "S*": "{>}{&s}",
        "A*": "{>}{&a}",
        "P-P": "{^.^}",
        'RUP': '{*<}',

        *U/P-P/S*/P-P/A*/P-P/RUP  ' u.s.a.'
        """

    def test_retro_upper18(self):
        r"""
        "TPAO": "foo",
        "KPATS": "{*-|}",
        "AES": "{^'s}",

        TPAO/AES/KPATS " Foo's"
        """

    def test_retro_upper19(self):
        r"""
        "TPAO": "foo",
        "KPATS": "{*<}",

        TPAO " foo"
        KPATS " FOO"
        * " foo"
        """

    def test_retro_upper20(self):
        r"""
        "TPAO": "foo",
        "KPATS": "{*<}",

        :spaces_after
        TPAO "foo "
        KPATS "FOO "
        * "foo "
        """

    def test_retro_upper21(self):
        r"""
        'TEFT': 'test',
        'RUP': '{:retro_case:upper_FIRST_word}',

        TEFT/RUP  " TEST"
        """

    def test_lower_first_char_1(self):
        r"""
        'TEFT': '{:CASE:Lower_First_Char}TEST',

        TEFT  ' tEST'
        """

    def test_upper1(self):
        r"""
        'TP*U': '{<}',
        'TEFT': 'test',
        '-G': '{^ing}',
        'PRE': '{pre^}',

        TP*U/TEFT/-G/PRE  " TESTING pre"
        """

    def test_upper2(self):
        r"""
        'TP*U': '{<}',
        'TEFT': 'test',
        '-G': '{^ing}',

        TP*U/TEFT/-G/TEFT  " TESTING test"
        """

    def test_upper3(self):
        r"""
        'TP*U': '{<}',
        'ST': 'it is',

        TP*U/ST  " IT is"
        """

    def test_upper4(self):
        r"""
        'TP*U': '{<}',
        'ST': 'it{ }is',

        TP*U/ST  " IT is"
        """

    def test_upper5(self):
        r"""
        'TP*U': '{<}',
        'TEFT': 'test',
        "W-G": "{^ing with}",

        TP*U/TEFT/W-G  " TESTING with"
        """

    def test_upper6(self):
        r"""
        'TP*U': '{<}',
        'P-': '{foo^}',
        '-S': '{^bar}',

        TP*U/P-/-S  " FOOBAR"
        """

    def test_upper7(self):
        r"""
        'TP*U': '{<}',
        'PRE': '{pre^}',
        'TEFT': 'test',
        '-G': '{^ing}',

        TP*U/PRE/TEFT/-G  " PRETESTING"
        """

    def test_upper8(self):
        r"""
        'TP*U': '{<}',
        'TEFT': 'test',
        "W-G": "{^ing with}",

        TP*U/TEFT/W-G/W-G  " TESTING withing with"
        """

    def test_upper9(self):
        r"""
        'TP*U': '{<}',
        'TEFT': 'test',
        "W": "with",

        TP*U/TEFT/W/W  " TEST with with"
        """

    def test_upper10(self):
        r"""
        'TEFT': '{:case:upper_first_word}test',
        '-G': '{^ing}',

        TEFT/-G  ' TESTING'
        """

    def test_attach_glue_and_carry_capitalize(self):
        r"""
        'PH*': '{&m}',
        'KW-GS': '{~|"}',

        PH*/KW-GS  ' m "'
        """

    def test_fingerspelling_retro_meta1(self):
        r"""
        'K': '{&c}',
        'A': '{&a}',
        'T': '{&t}',
        'UP': '{*<}',

        K/A/T  ' cat'
        UP     ' CAT'
        *      ' cat'
        """

    def test_fingerspelling_retro_meta2(self):
        r"""
        'TPH': '{>}{&n}',
        'O': '{>}{&o}',
        'UP': '{*<}',

        TPH/O/UP  ' NO'
        """

    def test_fingerspelling_retro_meta3(self):
        r"""
        'TEFT': '{>}{&n}{>}{&o}{*<}',

        TEFT  ' NO'
        """

    def test_word_1(self):
        r"""
        "KA*PS": "{MODE:CAPS}",
        "TEFT": "test",
        "-G": "{^ing}",
        'RUP': '{*-|}',

        KA*PS/TEFT/-G  ' TESTING'
        RUP            ' TESTING'
        """

    def test_word_2(self):
        r"""
        "KA*PS": "{MODE:CAPS}",
        "R*FT": "{MODE:RESET}",
        "TEFT": "test",
        "-G": "{^ing}",
        'RUL': '{*>}',

        KA*PS/TEFT/-G  ' TESTING'
        R*FT/RUL       ' tESTING'
        """

    def test_cat_burger_1(self):
        r"""
        "KAT": "cat",
        "O*PB":  "{^on}",
        "PWURG": "{*-|}{^burg}",
        "*ER": "{^er}",
        "PWURG/*ER": "burger",

        KAT/O*PB/PWURG  ' Cattonburg'
        *ER             ' catton burger'
        """

    def test_cat_burger_2(self):
        r"""
        "KAT": "cat",
        "O*PB":  "{^on}",
        "PWURG": "{*-|}{^burg}",
        "*ER": "{^er}",

        KAT/O*PB/PWURG  ' Cattonburg'
        *ER             ' Cattonburger'
        """

    def test_mirrored_capitalize(self):
        r"""
        'KPA': '{}{-|}',
        'TEFT': '{~|na^}{~|no^}{~|wri^}mo'

        KPA/TEFT  ' NaNoWriMo'
        """

    def test_mode_1a(self):
        r"""
        "PHO*D": "{MODE:CAMEL}",
        "TEFT": "test",

        :spaces_after
        TEFT   'test '
        PHO*D  'test '
        TEFT   'testtest'
        TEFT   'testtestTest'
        """

    def test_mode_1b(self):
        r"""
        "PHO*D": "{MODE:CAMEL}",
        "TEFT": "test",

        :spaces_before
        TEFT   ' test'
        PHO*D  ' test'
        TEFT   ' testtest'
        TEFT   ' testtestTest'
        """

    def test_mode_2a(self):
        r"""
        "PHO*D": "{MODE:CAMEL}",
        "TEFT": "test",
        "TKPWHRAOU": "{&g}{&l}{&u}{&e}"

        :spaces_after
        PHO*D  ''
        TEFT       'test'
        TKPWHRAOU  'testGlue'
        """

    def test_mode_2b(self):
        r"""
        "PHO*D": "{MODE:CAMEL}",
        "TEFT": "test",
        "TKPWHRAOU": "{&g}{&l}{&u}{&e}"

        :spaces_before
        PHO*D  ''
        TEFT       'test'
        TKPWHRAOU  'testGlue'
        """

    def test_mode_3a(self):
        r"""
        "PHO*D": "{MODE:CAMEL}",
        "TEFT": "test",
        "TKPWHRAOU": "{&g}{&l}{&u}{&e}"

        :spaces_after
        PHO*D  ''
        TKPWHRAOU  'glue'
        TEFT       'glueTest'
        """

    def test_mode_3b(self):
        r"""
        "PHO*D": "{MODE:CAMEL}",
        "TEFT": "test",
        "TKPWHRAOU": "{&g}{&l}{&u}{&e}"

        :spaces_before
        PHO*D  ''
        TKPWHRAOU  'glue'
        TEFT       'glueTest'
        """

    def test_mode_4(self):
        r"""
        "PHO*D": "{:mode:Camel}",
        "TEFT": "test",
        "TKPWHRAOU": "{&g}{&l}{&u}{&e}"

        PHO*D  ''
        TKPWHRAOU  'glue'
        TEFT       'glueTest'
        """

    def test_fingerspelling_1a(self):
        r"""
        'K': '{&c}',
        'A': '{&a}',
        'T': '{&t}',

        :spaces_after
        K/A/T  'cat '
        """

    def test_fingerspelling_1b(self):
        r"""
        'K': '{&c}',
        'A': '{&a}',
        'T': '{&t}',

        K/A/T  ' cat'
        """

    def test_fingerspelling_2a(self):
        r"""
        'K': '{-|}{&c}',
        'A': '{-|}{&a}',
        'T': '{-|}{&t}',

        :spaces_after
        K/A/T  'CAT '
        """

    def test_fingerspelling_2b(self):
        r"""
        'K': '{-|}{&c}',
        'A': '{-|}{&a}',
        'T': '{-|}{&t}',

        K/A/T  ' CAT'
        """

    def test_numbers_1a(self):
        r"""
        '': ''

        :spaces_after
        1-9  '19 '
        -79  '1979 '
        *    '19 '
        *    ''
        """

    def test_numbers_1b(self):
        r"""
        '': ''

        1-9  ' 19'
        -79  ' 1979'
        *    ' 19'
        *    ''
        """

    def test_raw_1a(self):
        r"""
        '': ''

        :spaces_after
        RAU   'RAU '
        TEGT  'RAU TEGT '
        *     'RAU '
        *     ''
        """

    def test_raw_1b(self):
        r"""
        '': ''

        RAU   ' RAU'
        TEGT  ' RAU TEGT'
        *     ' RAU'
        *     ''
        """

    def test_bug287(self):
        r"""
        "*6": "a",
        "R*S": "{*+}",

        *6   ' a'
        R*S  ' a a'
        """

    def test_bug470(self):
        r"""
        "0EU8": "80",
        "R*S": "{*+}",

        0EU8  ' 80'
        R*S   ' 8080'
        """

    def test_bug851(self):
        r"""
        "KUPBTS": "countries",
        "R-R": "{^}{#Return}{^}{-|}",

        :spaces_after
        KUPBTS "countries "
        R-R "countries"
        """

    def test_bug849_1(self):
        r"""
        "-P": ".",
        "*P": "{*}",
        "TKAOU": "due",
        "TKAO*U": "dew",

        TKAOU  ' due'
        -P      ' due .'
        *P     ' dew'
        """

    def test_bug849_2(self):
        r"""
        "KPA*": "{^}{-|}",
        "*P": "{*}",
        "TKAOU": "due",
        "TKAO*U": "dew",

        KPA*   ''
        TKAOU  'Due'
        *P     'Dew'
        """

    def test_carry_upper_spacing1(self):
        r"""
        "TEFT": "{<}test",
        "-G": "{^ing}",
        "S-P": "{^ ^}",
        "S-G": "something",

        TEFT/-G  ' TESTING'
        S-P      ' TESTING '
        S-G      ' TESTING something'
        """

    def test_carry_upper_spacing2(self):
        r"""
        "TEFT": "{<}test",
        "W-G": "{^ing with}",
        "S-G": "something",

        TEFT/W-G  ' TESTING with'
        S-G      ' TESTING with something'
        """

    def test_carry_upper_spacing3(self):
        r"""
        "TEFT": "{<}test",
        "-G": "{^ing}",
        "R-R": "{^\n^}",
        "S-G": "something",

        TEFT/-G  ' TESTING'
        R-R      ' TESTING\n'
        S-G      ' TESTING\nsomething'
        """

    def test_carry_upper_spacing4(self):
        r"""
        "TEFT": "{<}test",
        "W-G": "{^ing\twith}",

        TEFT/W-G  ' TESTING\twith'
        W-G      ' TESTING\twithing\twith'
        """

    def test_carry_upper_spacing5(self):
        r"""
        "TEFT": "{<}test",
        "-G": "{^ing}",
        "TA*B": "{^\t^}",
        "S-G": "something",

        TEFT/-G  ' TESTING'
        TA*B     ' TESTING\t'
        S-G      ' TESTING\tsomething'
        """

    def test_carry_upper_spacing6(self):
        r"""
        "TEFT": "{<}test",
        "W-G": "{^ing\nwith}",

        TEFT/W-G  ' TESTING\nwith'
        W-G       ' TESTING\nwithing\nwith'
        """

    def test_bug961(self):
        r"""
        "PHAED": "made",
        "KWREUS": "{^ies}",

        :spaces_after
        PHAED/KWREUS  'madies '
        *             'made '
        """

    def test_bug966_1(self):
        r"""
        "-G": "{^ing}",
        "KPA*L": "{<}",
        "TKPWAEUPL": "game",

        KPA*L/TKPWAEUPLG  ' GAMING'
        """

    def test_bug966_2(self):
        r"""
        "-G": "{^ing}",
        "KPA*L": "{<}",
        "TKPWAEUPL": "game",

        KPA*L/TKPWAEUPL/-G/*  ' GAME'
        """

    def test_bug980(self):
        r"""
        "PUFRPB": "punch",
        "HRAOEUPB": "line",
        "PUFRPB/HRAOEUPB": "punchline",
        "-S": "{^s}",
        "AFPS": "{*?}",

        PUFRPB/HRAOEUPBS  ' punchlines'
        AFPS              ' punch lines'
        """

    def test_not_a_macro_1(self):
        r"""
        "TEFT": "=",

        TEFT  ' ='
        """

    def test_not_a_macro_2(self):
        r"""
        "TEFT": "==",

        TEFT  ' =='
        """

    def test_not_a_macro_3(self):
        r"""
        "TEFT": "=>",

        TEFT  ' =>'
        """

    def test_not_a_macro_4(self):
        r"""
        "TEFT": "== 0",

        TEFT  ' == 0'
        """

    def test_not_a_macro_5(self):
        r"""
        "TEFT": "=not a macro",

        TEFT  ' =not a macro'
        """

    def test_not_a_macro_6(self):
        r"""
        "TEFT": "=not a macro:",

        TEFT  ' =not a macro:'
        """

    def test_bad_macro_1(self):
        r"""
        "TEFT": "=not_a_known_macro",

        TEFT  raise KeyError
        """

    def test_bad_macro_2(self):
        # Builtin macros not taking parameters.
        r"""
        "1": "=undo:param",
        "2": "=repeat_last_stroke:param",
        "3": "=retrospective_toggle_asterisk:param",
        "4": "=retrospective_delete_space:param",
        "5": "=retrospective_insert_space:param",

        1  raise AssertionError
        2  raise AssertionError
        3  raise AssertionError
        4  raise AssertionError
        5  raise AssertionError
        """

    def test_valid_macro_1(self):
        r"""
        "1": "=undo",
        "2": "=undo:",

        1   ""
        2   ""
        """

    def test_valid_macro_2(self, monkeypatch):
        r"""
        "TEFT": "=macro: params with spaces   ",

        TEFT   ""
        """

        def macro(translator, stroke, cmdline):
            assert cmdline == " params with spaces   "

        registry = Registry()
        registry.register_plugin("macro", "macro", macro)
        monkeypatch.setattr("plover.translation.registry", registry)

    def test_valid_macro_3(self, monkeypatch):
        r"""
        "TEFT": "=macro",

        TEFT   ""
        """

        def macro(translator, stroke, cmdline):
            assert cmdline == ""

        registry = Registry()
        registry.register_plugin("macro", "macro", macro)
        monkeypatch.setattr("plover.translation.registry", registry)

    def test_meta_attach_default(self):
        r"""
        'TEFT': 'test',
        'AT': '{:attach:attach}',

        TEFT/AT/TEFT  ' testattachtest'
        """

    def test_meta_attach_infix(self):
        r"""
        'TEFT': 'test',
        'AT': '{:attach:^attach^}',

        TEFT/AT/TEFT  ' testattachtest'
        """

    def test_meta_attach_prefix(self):
        r"""
        'TEFT': 'test',
        'AT': '{:attach:attach^}',

        TEFT/AT/TEFT  ' test attachtest'
        """

    def test_meta_attach_suffix(self):
        r"""
        'TEFT': 'test',
        'AT': '{:attach:^attach}',

        TEFT/AT/TEFT  ' testattach test'
        """

    def test_prefix_strokes(self):
        r"""
        "/S": "{prefix^}",
        "S": "{^suffix}",
        "O": "{O'^}{$}",

        S/S/O/S/S  " prefixsuffix O'prefixsuffix"
        """

    def test_melani_implicit_hyphens(self, with_melani_system):
        r"""
        :system Melani
        "15/SE/COhro": "XV secolo",
        "16/SE/COhro": "XVI secolo",

        15/SE/COhro/16/SE/COhro  " XV secolo XVI secolo"
        """

    def test_conditionals_1(self):
        r"""
        "*": "=undo",
        "S-": "{=(?i)t/true/false}",
        "TP-": "FALSE",
        "T-": "TRUE",

        S-   ' false'
        TP-  ' false FALSE'
        *    ' false'
        T-   ' true TRUE'
        *    ' false'
        S-   ' false false'
        TP-  ' false false FALSE'
        *    ' false false'
        T-   ' true true TRUE'
        """

    def test_conditionals_2(self):
        r"""
        "1": "{=(?i)([8aeiouxy]|11|dei|gn|ps|s[bcdfglmnpqrtv]|z)/agli/ai}",
        "2": "oc{^}chi",
        "3": "dei",
        "4": "sti{^}vali",

        1  ' ai'
        2  ' agli occhi'
        1  ' agli occhi ai'
        3  ' agli occhi agli dei'
        1  ' agli occhi agli dei ai'
        4  ' agli occhi agli dei agli stivali'
        """

    def test_conditionals_3(self):
        r"""
        "1": "{:if_next_matches:(?i)([8aeiouxy]|11|dei|gn|ps|s[bcdfglmnpqrtv]|z)/agli/ai}",
        "2": "chi",
        "3": "oc{^}chi",
        "4": "dei",
        "5": "sti{^}vali",

        :spaces_after
        2  'chi '
        1  'chi ai '
        3  'chi agli occhi '
        1  'chi agli occhi ai '
        4  'chi agli occhi agli dei '
        1  'chi agli occhi agli dei ai '
        5  'chi agli occhi agli dei agli stivali '
        """

    def test_conditionals_4(self):
        r"""
        "1": "{=(?i)([8aeiouxy]|11|dei|gn|ps|s[bcdfglmnpqrtv]|z)/agli/ai}",
        "2": "{=(?i)([8aeiouxy]|11|dei|gn|ps|s[bcdfglmnpqrtv]|z)/cogli/coi}",
        "3": "ci",

        1/2/1/3  ' ai cogli ai ci'
        """

    def test_conditionals_5(self):
        r"""
        "1": "{=(?i)([8aeiouxy]|11|dei|gn|ps|s[bcdfglmnpqrtv]|z)/agli/ai}",
        "2": "{=(?i)([8aeiouxy]|11|dei|gn|ps|s[bcdfglmnpqrtv]|z)/cogli/coi}",
        "3": "ci",

        :spaces_after
        1/2/1/3  'ai cogli ai ci '
        """

    def test_conditionals_6(self):
        r"""
        "*": "=undo",
        "S-": r'{=(?i)tr\/ue/tr\/ue/fa\\lse}',
        "TP-": r'FA\LSE',
        "T-": 'TR/UE',

        S-   r' fa\lse'
        TP-  r' fa\lse FA\LSE'
        *    r' fa\lse'
        T-   r' tr/ue TR/UE'
        *    r' fa\lse'
        S-   r' fa\lse fa\lse'
        TP-  r' fa\lse fa\lse FA\LSE'
        *    r' fa\lse fa\lse'
        T-   r' tr/ue tr/ue TR/UE'
        """

    def test_bug_1448_1(self, with_korean_system):
        # Translator tries to represent a previous stroke
        # from a different system using the current one.
        #
        # This test would throw a `ValueError` exception
        # (invalid keys mask) in the translator when
        # trying to represent the `ㅎㅁㄱㅈㄴ-ㄴㅅㅈㅁ`
        # stroke with the `English Stenotype` system.
        r"""
        'TEFT': 'test'
        'TEFT/-G': 'testing'

        :system 'Korean Modern C'
        ㅎㅁㄱㅈㄴ-ㄴㅅㅈㅁ  ' ㅎㅁㄱㅈㄴ-ㄴㅅㅈㅁ'
        :system 'English Stenotype'
        TEFT  ' ㅎㅁㄱㅈㄴ-ㄴㅅㅈㅁ test'
        """

    def test_bug_1448_2(self, with_korean_system):
        # Translator tries to represent a previous stroke
        # from a different system using the current one.
        #
        # This test would trigger a translator lookup for
        # `#STKP/-G` because `#STKP` (English Stenotype)
        # and `12345` (Korean Modern C) have the same keys
        # mask.
        r"""
        '#STKP/-G': 'game over'

        :system 'Korean Modern C'
        12345  ' 12345'
        :system 'English Stenotype'
        -G  ' 12345 -G'
        """
