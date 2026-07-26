import inspect
import itertools

import pytest

from plover.key_combo import parse_key_combo


def generate_combo_tests(test_id, *params, key_name_to_key_code=None):
    yield ("id", test_id)
    if key_name_to_key_code is not None:
        yield ("key_name_to_key_code", key_name_to_key_code)
    for iterables in params:
        iterables = [i if isinstance(i, (tuple, list)) else (i,) for i in iterables]
        if len(iterables) < 2:
            iterables.append(("",))
        for (
            combo_string,
            parse_result,
        ) in itertools.product(*iterables):
            yield (("parse", combo_string, parse_result),)


# Test directives:
# - id TEST_IDENTIFIER
# - key_name_to_key_code KEY_NAME_TO_KEY_CODE_FUNCTION
# - parse COMBO_STRING KEY_EVENTS
KEY_COMBO_TESTS = tuple(
    itertools.chain(
        (("key_name_to_key_code", lambda k: k),),
        # No-op.
        generate_combo_tests(
            "no-op",
            (("", "   "), ""),
        ),
        # Syntax error:
        generate_combo_tests(
            "syntax_error",
            (
                (
                    # - invalid character
                    "Return,",
                    "Return&",
                    "Ret. urn <",
                    "exclam ! foo",
                    "shift[a]",
                    # - unbalanced `)`
                    ") arg",
                    "arg )",
                    "arg())",
                    "arg(x) )",
                    # - unbalanced `(`
                    "test(",
                    "( grr",
                    "foo ( bar",
                    "foo (bar ( ",
                    "foo ((",
                    # - [-+]key() is not valid
                    "+foo ()",
                    "+foo()",
                ),
                SyntaxError,
            ),
        ),
        # Pressing an already pressed key.
        generate_combo_tests(
            "already_pressed",
            (
                (
                    "foo(foo)",
                    "Foo(foO)",
                    "foo(fOo(arg))",
                    "foo(bar(Foo))",
                    "foo(bar(foo(x)))",
                ),
                ValueError,
            ),
        ),
        # Stacking.
        generate_combo_tests(
            "stacking",
            # 1 is not a valid identifier, but still a valid key name.
            ("1", "+1 -1"),
            (("Shift_l", "SHIFT_L"), "+shift_l -shift_l"),
            # Case does not matter.
            (("a", " A "), "+a -a"),
            (("a(b c)", "a ( b c   )"), "+a +b -b +c -c -a"),
            (("a(bc)", " a(  Bc )"), "+a +bc -bc -a"),
            (
                ("a(bc(d)e f(g) h())i j"),
                "+a +bc +d -d -bc +e -e +f +g -g -f +h -h -a +i -i +j -j",
            ),
            (
                ("foo () bar ( foo a b c (d))", "fOo () Bar ( FOO a B c (D))"),
                "+foo -foo +bar +foo -foo +a -a +b -b +c +d -d -c -bar",
            ),
        ),
        # Invalid key name.
        generate_combo_tests(
            "invalid_key",
            ("1 (c) 2 bad 3 (a b c)", ValueError),
            key_name_to_key_code={c: c for c in "123abc"}.get,
        ),
        # Same key code, multiple key names.
        generate_combo_tests(
            "aliasing",
            ("1 exclam", "+10 -10 +10 -10"),
            (("1 ( exclam )", "exclam(1)"), ValueError),
            key_name_to_key_code={"1": "10", "exclam": "10"}.get,
        ),
    )
)


def parametrize(tests):
    key_name_to_key_code = None
    test_id = None
    args = []
    ids = []
    for t in tests:
        if t[0] == "key_name_to_key_code":
            key_name_to_key_code = t[1]
        elif t[0] == "id":
            test_id = t[1]
        else:
            assert key_name_to_key_code is not None
            assert test_id is not None
            args.append((key_name_to_key_code, t))
            ids.append(test_id)
    return pytest.mark.parametrize(
        ("key_name_to_key_code", "instructions"), args, ids=ids
    )


@parametrize(KEY_COMBO_TESTS)
def test_key_combo(key_name_to_key_code, instructions):
    def repr_expected(result):
        assert isinstance(result, str)
        return [s.strip() for s in result.split()]

    def repr_key_events(events):
        assert isinstance(events, list)
        return ["{}{}".format("+" if pressed else "-", key) for key, pressed in events]

    for action, *args in instructions:
        if action == "parse":
            combo_string, key_events = args
            if inspect.isclass(key_events):
                with pytest.raises(key_events):
                    parse_key_combo(
                        combo_string, key_name_to_key_code=key_name_to_key_code
                    )
            else:
                assert repr_key_events(
                    parse_key_combo(
                        combo_string, key_name_to_key_code=key_name_to_key_code
                    )
                ) == repr_expected(key_events)
        else:
            raise ValueError(args[0])
