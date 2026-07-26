# Copyright (c) 2013 Hesky Fisher
# See LICENSE.txt for details.

"""Unit tests for translation.py."""

import ast
import copy
import operator
from collections import namedtuple

import pytest

from plover.oslayer.config import PLATFORM
from plover.steno import Stroke, normalize_steno
from plover.steno_dictionary import StenoDictionary, StenoDictionaryCollection
from plover.translation import (
    Translation,
    Translator,
    _State,
    escape_translation,
    unescape_translation,
)
from plover_build_utils.testing import parametrize
from plover_build_utils.testing import steno_to_stroke as stroke

if PLATFORM == "mac":
    BACK_STRING = "{#Alt_L(BackSpace)}{^}"
else:
    BACK_STRING = "{#Control_L(BackSpace)}{^}"


def test_no_translation():
    t = Translation([stroke("S"), stroke("T")], None)
    assert t.strokes == [stroke("S"), stroke("T")]
    assert t.rtfcre == ("S", "T")
    assert t.english is None


def test_translation():
    t = Translation([stroke("S"), stroke("T")], "translation")
    assert t.strokes == [stroke("S"), stroke("T")]
    assert t.rtfcre == ("S", "T")
    assert t.english == "translation"


class TestTranslatorStateSize:
    class FakeState(_State):
        def __init__(self):
            _State.__init__(self)
            self.restrict_calls = []

        def restrict_size(self, n):
            self.restrict_calls.append(n)

    def _check_size_call(self, size):
        assert self.s.restrict_calls[-1] == size

    def _check_no_size_call(self):
        assert self.s.restrict_calls == []

    def clear(self):
        self.s.restrict_calls = []

    def setup_method(self):
        self.t = Translator()
        self.s = type(self).FakeState()
        self.t._state = self.s
        self.d = StenoDictionary()
        self.dc = StenoDictionaryCollection([self.d])
        self.t.set_dictionary(self.dc)

    @pytest.mark.parametrize(
        "key",
        (
            ("S",),
            ("S", "PT", "-Z", "TOP"),
        ),
    )
    def test_dictionary_update_grows_size(self, key):
        self.d[key] = "key"
        self.t.translate(stroke("T-"))
        self._check_size_call(len(key))

    def test_dictionary_update_no_grow(self):
        self.t.set_min_undo_length(4)
        self._check_size_call(4)
        self.clear()
        self.d[("S", "T")] = "nothing"
        self.t.translate(stroke("T-"))
        self._check_size_call(4)

    def test_dictionary_update_shrink(self):
        self.d[("S", "T", "P", "-Z", "-D")] = "1"
        self.t.translate(stroke("T-"))
        self._check_size_call(5)
        self.clear()
        self.d[("A", "P")] = "2"
        self.t.translate(stroke("T-"))
        self._check_size_call(5)
        self.clear()
        del self.d[("S", "T", "P", "-Z", "-D")]
        self.t.translate(stroke("T-"))
        self._check_size_call(2)

    def test_dictionary_update_no_shrink(self):
        self.t.set_min_undo_length(7)
        self.d[("S", "T", "P", "-Z", "-D")] = "1"
        del self.d[("S", "T", "P", "-Z", "-D")]
        self._check_size_call(7)

    def test_translation_calls_restrict(self):
        self.t.translate(stroke("S"))
        self._check_size_call(0)


def test_listeners():
    output1 = []

    def listener1(undo, do, prev):
        output1.append((undo, do, prev))

    output2 = []

    def listener2(undo, do, prev):
        output2.append((undo, do, prev))

    t = Translator()
    s = stroke("S")
    tr = Translation([s], None)
    expected_output = [([], [tr], [tr])]

    t.translate(s)

    t.add_listener(listener1)
    t.translate(s)
    assert output1 == expected_output

    del output1[:]
    t.add_listener(listener2)
    t.translate(s)
    assert output1 == expected_output
    assert output2 == expected_output

    del output1[:]
    del output2[:]
    t.add_listener(listener2)
    t.translate(s)
    assert output1 == expected_output
    assert output2 == expected_output

    del output1[:]
    del output2[:]
    t.remove_listener(listener1)
    t.translate(s)
    assert output1 == []
    assert output2 == expected_output

    del output1[:]
    del output2[:]
    t.remove_listener(listener2)
    t.translate(s)
    assert output1 == []
    assert output2 == []


def test_changing_state():
    output = []

    def listener(undo, do, prev):
        prev = list(prev) if prev else None
        output.append((undo, do, prev))

    d = StenoDictionary()
    d[("S", "P")] = "hi"
    dc = StenoDictionaryCollection([d])
    t = Translator()
    t.set_dictionary(dc)
    t.translate(stroke("T"))
    t.translate(stroke("S"))
    s = copy.deepcopy(t.get_state())

    t.add_listener(listener)

    expected = [
        (
            [Translation([stroke("S")], None)],
            [Translation([stroke("S"), stroke("P")], "hi")],
            [Translation([stroke("T")], None)],
        )
    ]
    t.translate(stroke("P"))
    assert output == expected

    del output[:]
    t.set_state(s)
    t.translate(stroke("P"))
    assert output == expected

    del output[:]
    t.clear_state()
    t.translate(stroke("P"))
    assert output == [([], [Translation([stroke("P")], None)], None)]

    del output[:]
    t.set_state(s)
    t.translate(stroke("P"))
    assert output == [
        (
            [],
            [Translation([stroke("P")], None)],
            [Translation([stroke("S"), stroke("P")], "hi")],
        )
    ]


def test_translator():
    # It's not clear that this test is needed anymore. There are separate
    # tests for _translate_stroke and test_translate_calls_translate_stroke
    # makes sure that translate calls it properly. But since I already wrote
    # this test I'm going to keep it.

    class Output:
        def __init__(self):
            self._output = []

        def write(self, undo, do, prev):
            for t in undo:
                self._output.pop()
            for t in do:
                if t.english:
                    self._output.append(t.english)
                else:
                    self._output.append("/".join(t.rtfcre))

        def get(self):
            return " ".join(self._output)

        def clear(self):
            del self._output[:]

    d = StenoDictionary()
    out = Output()
    t = Translator()
    dc = StenoDictionaryCollection([d])
    t.set_dictionary(dc)
    t.add_listener(out.write)

    t.translate(stroke("S"))
    assert out.get() == "S"
    t.translate(stroke("T"))
    assert out.get() == "S T"
    t.translate(stroke("*"))
    assert out.get() == "S"
    t.translate(stroke("*"))
    # Undo buffer ran out
    assert out.get() == "S " + BACK_STRING

    t.set_min_undo_length(3)
    out.clear()
    t.translate(stroke("S"))
    assert out.get() == "S"
    t.translate(stroke("T"))
    assert out.get() == "S T"
    t.translate(stroke("*"))
    assert out.get() == "S"
    t.translate(stroke("*"))
    assert out.get() == ""

    out.clear()
    d[("S",)] = "t1"
    d[("T",)] = "t2"
    d[("S", "T")] = "t3"

    t.translate(stroke("S"))
    assert out.get() == "t1"
    t.translate(stroke("T"))
    assert out.get() == "t3"
    t.translate(stroke("T"))
    assert out.get() == "t3 t2"
    t.translate(stroke("S"))
    assert out.get() == "t3 t2 t1"
    t.translate(stroke("*"))
    assert out.get() == "t3 t2"
    t.translate(stroke("*"))
    assert out.get() == "t3"
    t.translate(stroke("*"))
    assert out.get() == "t1"
    t.translate(stroke("*"))
    assert out.get() == ""

    t.translate(stroke("S"))
    assert out.get() == "t1"
    t.translate(stroke("T"))
    assert out.get() == "t3"
    t.translate(stroke("T"))
    assert out.get() == "t3 t2"

    d[("S", "T", "T")] = "t4"
    d[("S", "T", "T", "S")] = "t5"

    t.translate(stroke("S"))
    assert out.get() == "t5"
    t.translate(stroke("*"))
    assert out.get() == "t3 t2"
    t.translate(stroke("*"))
    assert out.get() == "t3"
    t.translate(stroke("T"))
    assert out.get() == "t4"
    t.translate(stroke("S"))
    assert out.get() == "t5"
    t.translate(stroke("S"))
    assert out.get() == "t5 t1"
    t.translate(stroke("*"))
    assert out.get() == "t5"
    t.translate(stroke("*"))
    assert out.get() == "t4"
    t.translate(stroke("*"))
    assert out.get() == "t3"
    t.translate(stroke("*"))
    assert out.get() == "t1"
    t.translate(stroke("*"))
    assert out.get() == ""

    d.clear()

    s = stroke("S")
    t.translate(s)
    t.translate(s)
    t.translate(s)
    t.translate(s)
    s = stroke("*")
    t.translate(s)
    t.translate(s)
    t.translate(s)
    t.translate(s)
    # Not enough undo to clear output.
    assert out.get() == "S " + BACK_STRING

    out.clear()
    t.remove_listener(out.write)
    t.translate(stroke("S"))
    assert out.get() == ""


class TestState:
    def setup_method(self):
        self.a = Translation([stroke("S")], None)
        self.b = Translation([stroke("T"), stroke("-D")], None)
        self.c = Translation([stroke("-Z"), stroke("P"), stroke("T*")], None)

    def test_prev_list0(self):
        s = _State()
        assert s.prev() is None

    def test_prev_list1(self):
        s = _State()
        s.translations = [self.a]
        assert s.prev() == [self.a]

    def test_prev_list2(self):
        s = _State()
        s.translations = [self.a, self.b]
        assert s.prev() == [self.a, self.b]

    def test_prev_tail1(self):
        s = _State()
        s.translations = [self.a]
        s.tail = self.b
        assert s.prev() == [self.a]

    def test_prev_tail0(self):
        s = _State()
        s.tail = self.b
        assert s.prev() == [self.b]

    def test_restrict_size_zero_on_empty(self):
        s = _State()
        s.restrict_size(0)
        assert s.translations == []
        assert s.tail is None

    def test_restrict_size_zero_on_one_stroke(self):
        s = _State()
        s.translations = [self.a]
        s.restrict_size(0)
        assert s.translations == [self.a]
        assert s.tail is None

    def test_restrict_size_to_exactly_one_stroke(self):
        s = _State()
        s.translations = [self.a]
        s.restrict_size(1)
        assert s.translations == [self.a]
        assert s.tail is None

    def test_restrict_size_to_one_on_two_strokes(self):
        s = _State()
        s.translations = [self.b]
        s.restrict_size(1)
        assert s.translations == [self.b]
        assert s.tail is None

    def test_restrict_size_to_one_on_two_translations(self):
        s = _State()
        s.translations = [self.b, self.a]
        s.restrict_size(1)
        assert s.translations == [self.a]
        assert s.tail == self.b

    def test_restrict_size_to_one_on_two_translations_too_big(self):
        s = _State()
        s.translations = [self.a, self.b]
        s.restrict_size(1)
        assert s.translations == [self.b]
        assert s.tail == self.a

    def test_restrict_size_lose_translations(self):
        s = _State()
        s.translations = [self.a, self.b, self.c]
        s.restrict_size(2)
        assert s.translations == [self.c]
        assert s.tail == self.b

    def test_restrict_size_multiple_translations(self):
        s = _State()
        s.translations = [self.a, self.b, self.c]
        s.restrict_size(5)
        assert s.translations == [self.b, self.c]
        assert s.tail == self.a


class TestTranslateStroke:
    DICT_COLLECTION_CLASS = StenoDictionaryCollection

    class CaptureOutput:
        Output = namedtuple("Output", "undo do prev")

        def __init__(self):
            self.output = []

        def __call__(self, undo, new, prev):
            prev = list(prev) if prev else None
            self.output = self.Output(undo, new, prev)

    def t(self, strokes):
        """A quick way to make a translation."""
        strokes = [stroke(x) for x in strokes.split("/")]
        key = tuple(s.rtfcre for s in strokes)
        translation = self.dc.lookup(key)
        return Translation(strokes, translation)

    def lt(self, translations):
        """A quick way to make a list of translations."""
        return [self.t(x) for x in translations.split()]

    def define(self, key, value):
        key = normalize_steno(key)
        self.d[key] = value

    def translate(self, steno):
        self.tlor.translate(stroke(steno))

    def _check_translations(self, expected):
        # Hide from traceback on assertions (reduce output size for failed tests).
        __tracebackhide__ = operator.methodcaller("errisinstance", AssertionError)
        msg = f"""
        translations:
            results: {self.s.translations}
            expected: {expected}
        """
        assert self.s.translations == expected, msg

    def _check_output(self, undo, do, prev):
        # Hide from traceback on assertions (reduce output size for failed tests).
        __tracebackhide__ = operator.methodcaller("errisinstance", AssertionError)
        msg = """
        output:
            results: -%s
                     +%s
                     [%s]
            expected: -%s
                      +%s
                      [%s]
        """ % (self.o.output + (undo, do, prev))
        assert self.o.output == (undo, do, prev), msg

    def setup_method(self):
        self.d = StenoDictionary()
        self.dc = self.DICT_COLLECTION_CLASS([self.d])
        self.s = _State()
        self.o = self.CaptureOutput()
        self.tlor = Translator()
        self.tlor.set_dictionary(self.dc)
        self.tlor.add_listener(self.o)
        self.tlor.set_state(self.s)

    def test_first_stroke(self):
        self.translate("-B")
        self._check_translations(self.lt("-B"))
        self._check_output([], self.lt("-B"), None)

    def test_second_stroke(self):
        self.define("S/P", "spiders")
        self.s.translations = self.lt("S")
        self.translate("-T")
        self._check_translations(self.lt("S -T"))
        self._check_output([], self.lt("-T"), self.lt("S"))

    def test_second_stroke_tail(self):
        self.s.tail = self.t("T/A/EU/L")
        self.translate("-E")
        self._check_translations(self.lt("E"))
        self._check_output([], self.lt("E"), self.lt("T/A/EU/L"))

    def test_with_translation_1(self):
        self.define("S", "is")
        self.define("-T", "that")
        self.s.translations = self.lt("S")
        self.tlor.set_min_undo_length(2)
        self.translate("-T")
        self._check_translations(self.lt("S -T"))
        self._check_output([], self.lt("-T"), self.lt("S"))
        assert self.o.output.do[0].english == "that"

    def test_with_translation_2(self):
        self.define("S", "is")
        self.define("-T", "that")
        self.s.translations = self.lt("S")
        self.tlor.set_min_undo_length(1)
        self.translate("-T")
        self._check_translations(self.lt("-T"))
        self._check_output([], self.lt("-T"), self.lt("S"))
        assert self.o.output.do[0].english == "that"

    def test_finish_two_translation(self):
        self.define("S/T", "hello")
        self.s.translations = self.lt("S")
        self.translate("T")
        self._check_translations(self.lt("S/T"))
        self._check_output(self.lt("S"), self.lt("S/T"), None)
        assert self.o.output.do[0].english == "hello"
        assert self.o.output.do[0].replaced == self.lt("S")

    def test_finish_three_translation(self):
        self.define("S/T/-B", "bye")
        self.s.translations = self.lt("S T")
        self.translate("-B")
        self._check_translations(self.lt("S/T/-B"))
        self._check_output(self.lt("S T"), self.lt("S/T/-B"), None)
        assert self.o.output.do[0].english == "bye"
        assert self.o.output.do[0].replaced == self.lt("S T")

    def test_replace_translation(self):
        self.define("S/T/-B", "longer")
        self.s.translations = self.lt("S/T")
        self.translate("-B")
        self._check_translations(self.lt("S/T/-B"))
        self._check_output(self.lt("S/T"), self.lt("S/T/-B"), None)
        assert self.o.output.do[0].english == "longer"
        assert self.o.output.do[0].replaced == self.lt("S/T")

    def test_undo(self):
        self.s.translations = self.lt("POP")
        self.translate("*")
        self._check_translations([])
        self._check_output(self.lt("POP"), [], None)

    def test_empty_undo(self):
        self.translate("*")
        self._check_translations([])
        self._check_output([], [Translation([Stroke("*")], BACK_STRING)], None)

    def test_undo_translation(self):
        self.define("P/P", "pop")
        self.translate("P")
        self.translate("P")
        self.translate("*")
        self._check_translations(self.lt("P"))
        self._check_output(self.lt("P/P"), self.lt("P"), None)

    def test_undo_longer_translation(self):
        self.define("P/P/-D", "popped")
        self.translate("P")
        self.translate("P")
        self.translate("-D")
        self.translate("*")
        self._check_translations(self.lt("P P"))
        self._check_output(self.lt("P/P/-D"), self.lt("P P"), None)

    def test_undo_tail(self):
        self.s.tail = self.t("T/A/EU/L")
        self.translate("*")
        self._check_translations([])
        self._check_output([], [Translation([Stroke("*")], BACK_STRING)], [self.s.tail])

    def test_suffix_folding(self):
        self.define("K-L", "look")
        self.define("-G", "{^ing}")
        lt = self.lt("K-LG")
        lt[0].english = "look {^ing}"
        self.translate("K-LG")
        self._check_translations(lt)

    def test_suffix_folding_multi_stroke(self):
        self.define("E/HR", "he will")
        self.define("-S", "{^s}")
        self.translate("E")
        self.translate("HR-S")
        output = " ".join(t.english for t in self.s.translations)
        assert output == "he will {^s}"

    def test_suffix_folding_doesnt_interfere(self):
        self.define("E/HR", "he will")
        self.define("-S", "{^s}")
        self.define("E", "he")
        self.define("HR-S", "also")
        self.translate("E")
        self.translate("HR-S")
        output = " ".join(t.english for t in self.s.translations)
        assert output == "he also"

    def test_suffix_folding_no_suffix(self):
        self.define("K-L", "look")
        lt = self.lt("K-LG")
        assert lt[0].english is None
        self.translate("K-LG")
        self._check_translations(lt)

    def test_suffix_folding_no_main(self):
        self.define("-G", "{^ing}")
        lt = self.lt("K-LG")
        assert lt[0].english is None
        self.translate("K-LG")
        self._check_translations(lt)

    def test_retrospective_insert_space(self):
        self.define("T/E/S/T", "a longer key")
        self.define("PER", "perfect")
        self.define("SWAEUGS", "situation")
        self.define("PER/SWAEUGS", "persuasion")
        self.define("SP*", "{*?}")
        self.translate("PER")
        self.translate("SWAEUGS")
        self.translate("SP*")
        lt = self.lt("PER")
        undo = self.lt("PER/SWAEUGS")
        undo[0].replaced = lt
        do = self.lt("SP*")
        do[0].english = "perfect situation"
        do[0].is_retrospective_command = True
        do[0].replaced = undo
        self._check_translations(do)
        self._check_output(undo, do, None)

    def test_retrospective_insert_space_undefined(self):
        # Should work when beginning or ending strokes aren't defined
        self.define("T/E/S/T", "a longer key")
        self.define("STWR/STWR", "test")
        self.define("SP*", "{*?}")
        self.translate("STWR")
        self.translate("STWR")
        self.translate("SP*")
        lt = self.lt("STWR")
        undo = self.lt("STWR/STWR")
        undo[0].replaced = lt
        do = self.lt("SP*")
        do[0].english = "STWR STWR"
        do[0].is_retrospective_command = True
        do[0].replaced = undo
        self._check_translations(do)
        self._check_output(undo, do, None)

    def test_retrospective_delete_space(self):
        self.define("T/E/S/T", "a longer key")
        self.define("K", "kick")
        self.define("PW", "back")
        self.define("SP*", "{*!}")
        self.translate("K")
        self.translate("PW")
        self.translate("SP*")
        undo = self.lt("K PW")
        do = self.lt("SP*")
        do[0].english = "kick{^~|^}back"
        do[0].is_retrospective_command = True
        do[0].replaced = undo
        self._check_translations(do)
        self._check_output(undo, do, None)

    def test_retrospective_delete_space_with_number(self):
        self.define("T/E/S/T", "a longer key")
        self.define("U", "user")
        self.define("SP*", "{*!}")
        self.translate("U")
        self.translate("1-")
        self.translate("SP*")
        undo = self.lt("U 1-")
        do = self.lt("SP*")
        do[0].english = "user{^~|^}{&1}"
        do[0].is_retrospective_command = True
        do[0].replaced = undo
        self._check_translations(do)
        self._check_output(undo, do, None)

    def test_retrospective_delete_space_with_period(self):
        self.define("T/E/S/T", "a longer key")
        self.define("P-P", "{.}")
        self.define("SH*", "zshrc")
        self.define("SP*", "{*!}")
        self.translate("P-P")
        self.translate("SH*")
        self.translate("SP*")
        undo = self.lt("P-P SH*")
        do = self.lt("SP*")
        do[0].english = "{.}{^~|^}zshrc"
        do[0].is_retrospective_command = True
        do[0].replaced = undo
        self._check_translations(do)
        self._check_output(undo, do, None)

    def test_retrospective_toggle_asterisk(self):
        self.define("T/E/S/T", "a longer key")
        self.define("S", "see")
        self.define("S*", "sea")
        self.define("A*", "{*}")
        self.translate("S")
        self.translate("A*")
        self._check_translations(self.lt("S*"))
        self._check_output(self.lt("S"), self.lt("S*"), None)

    def test_retrospective_toggle_empty(self):
        self.define("A*", "{*}")
        self.translate("A*")
        self._check_translations(self.lt(""))
        assert self.o.output == []

    def test_retrospective_toggle_asterisk_replaced1(self):
        self.define("P-P", "{.}")
        self.define("SKEL", "cancel")
        self.define("SKEL/TO-PB", "skeleton")
        self.define("SKEL/TO*PB", "not skeleton!")
        self.define("A*", "{*}")
        self.translate("P-P")
        self.translate("SKEL")
        self.translate("TO-PB")
        self.translate("A*")
        self._check_translations(self.lt("SKEL/TO*PB"))
        self._check_output(self.lt("SKEL/TO-PB"), self.lt("SKEL/TO*PB"), self.lt("P-P"))

    def test_retrospective_toggle_asterisk_replaced2(self):
        self.define("P-P", "{.}")
        self.define("SKEL", "cancel")
        self.define("SKEL/TO-PB", "skeleton")
        self.define("TO*PB", "{^ton}")
        self.define("A*", "{*}")
        self.translate("P-P")
        self.translate("SKEL")
        self.translate("TO-PB")
        self.translate("A*")
        self._check_translations(self.lt("SKEL TO*PB"))
        self._check_output(self.lt("SKEL/TO-PB"), self.lt("SKEL TO*PB"), self.lt("P-P"))

    def test_repeat_last_stroke1(self):
        self.define("T/E/S/T", "a longer key")
        self.define("TH", "this")
        self.define("R*", "{*+}")
        self.translate("TH")
        self.translate("R*")
        undo = []
        do = self.lt("TH")
        state = self.lt("TH TH")
        self._check_translations(state)
        self._check_output(undo, do, do)

    def test_repeat_last_stroke2(self):
        self.define("T/E/S/T", "a longer key")
        self.define("THA", "that")
        self.define("R*", "{*+}")
        self.translate("THA")
        self.translate("R*")
        undo = []
        do = self.lt("THA")
        state = self.lt("THA THA")
        self._check_translations(state)
        self._check_output(undo, do, do)

    def test_untranslate_translation(self):
        self.tlor.set_min_undo_length(2)
        self.define("TH", "this")
        self.define("THA", "that")
        self.translate("TH")
        self.translate("THA")
        self.tlor.untranslate_translation(self.t("THA"))
        self.tlor.untranslate_translation(self.t("TH"))
        self.tlor.flush()
        self._check_output(self.lt("TH THA"), [], None)


ESCAPE_UNESCAPE_TRANSLATION_TESTS = (
    # No change.
    lambda: ("foobar", "foobar"),
    lambda: (r"\\", r"\\"),
    lambda: ("\\\\\\", "\\\\\\"),  # -> \\\
    # Basic support: \n, \r, \t.
    lambda: ("\n", r"\n"),
    lambda: ("\r", r"\r"),
    lambda: ("\t", r"\t"),
    # Allow a literal \n, \r, or \t by doubling the \.
    lambda: (r"\n", r"\\n"),
    lambda: (r"\r", r"\\r"),
    lambda: (r"\t", r"\\t"),
    lambda: (r"\\n", r"\\\n"),
    lambda: (r"\\r", r"\\\r"),
    lambda: (r"\\t", r"\\\t"),
    # A little more complex.
    lambda: ("\tfoo\nbar\r", r"\tfoo\nbar\r"),
    lambda: ("\\tfoo\\nbar\\r", r"\\tfoo\\nbar\\r"),
)


@parametrize(ESCAPE_UNESCAPE_TRANSLATION_TESTS)
def test_escape_unescape_translation(raw, escaped):
    assert unescape_translation(escaped) == raw
    assert escape_translation(raw) == escaped


class TestNoUnnecessaryLookups(TestTranslateStroke):
    # Custom dictionary collection class for tracking lookups.
    class DictTracy(StenoDictionaryCollection):
        def __init__(self, dicts):
            super().__init__(dicts)
            self.lookup_history = []

        def lookup(self, key):
            self.lookup_history.append(key)
            return super().lookup(key)

    DICT_COLLECTION_CLASS = DictTracy

    def _prepare_state(self, definitions, translations):
        if definitions:
            for steno, english in ast.literal_eval("{" + definitions + "}").items():
                self.define(steno, english)
        translations = self.lt(translations)
        for t in translations:
            for s in t.strokes:
                self.translate(s.rtfcre)
        state = translations[len(translations) - self.dc.longest_key :]
        self._check_translations(state)
        self.dc.lookup_history.clear()

    def _check_lookup_history(self, expected):
        # Hide from traceback on assertions (reduce output size for failed tests).
        __tracebackhide__ = operator.methodcaller("errisinstance", AssertionError)
        result = ["/".join(key) for key in self.dc.lookup_history]
        expected = expected.split()
        msg = f"""
        lookup history:
            results: {result}
            expected: {expected}
        """
        assert result == expected, msg

    def test_zero_lookups(self):
        # No lookups at all if longest key is zero.
        self.translate("TEFT")
        self._check_lookup_history("")
        self._check_translations(self.lt("TEFT"))

    def test_no_prefix_lookup_over_the_longest_key_limit(self):
        self._prepare_state(
            """
            "HROPBG/EFT/KAOE": "longest key",
            "HRETS": "let's",
            "TKO": "do",
            "SPH": "some",
            "TEFT": "test",
            "-G": "{^ing}",
            """,
            "HRETS TKO SPH TEFT",
        )
        self.translate("-G")
        self._check_lookup_history(
            # Macros.
            """
            /-G
            -G
            """
            # Others.
            """
            SPH/TEFT/-G
            /TEFT/-G TEFT/-G
            """
        )

    def test_no_duplicate_lookups_for_longest_no_suffix_match(self):
        self._prepare_state(
            """
            "TEFT": "test",
            "-G": "{^ing}",
            """,
            "TEFT",
        )
        self.translate("TEFGT")
        self._check_lookup_history(
            # Macros.
            """
            TEFGT
            """
            # No suffix.
            """
            """
            # With suffix.
            """
            -G TEFT
            """
        )

    def test_lookup_suffixes_once(self):
        self._prepare_state(
            """
            "HROPBG/EFT/KAOE": "longest key",
            "HRETS": "let's",
            "TEFT": "test",
            "SPH": "some",
            "SUFBGS": "suffix",
            "-G": "{^ing}",
            "-S": "{^s}",
            "-D": "{^ed}",
            "-Z": "{^s}",
            """,
            "HRETS TEFT SPH",
        )
        self.translate("SUFBGSZ")
        self._check_lookup_history(
            # Macros.
            """
            /SUFBGSZ
            SUFBGSZ
            """
            # Without suffix.
            """
            TEFT/SPH/SUFBGSZ
            /SPH/SUFBGSZ
            SPH/SUFBGSZ
            """
            # Suffix lookups.
            """
            -Z -S -G
            TEFT/SPH/SUFBGS TEFT/SPH/SUFBGZ TEFT/SPH/SUFBSZ
            /SPH/SUFBGS /SPH/SUFBGZ /SPH/SUFBSZ
            SPH/SUFBGS SPH/SUFBGZ SPH/SUFBSZ
            /SUFBGS /SUFBGZ /SUFBSZ
            SUFBGS
            """
        )
