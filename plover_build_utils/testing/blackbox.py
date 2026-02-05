import ast
import functools
import inspect
import operator
import re
import shlex
import textwrap

from plover import system
from plover.formatting import Formatter
from plover.steno import normalize_steno
from plover.steno_dictionary import StenoDictionary
from plover.translation import Translator

from .output import CaptureOutput
from .steno import steno_to_stroke


BLACKBOX_OUTPUT_RX = re.compile("r?['\"]")


def blackbox_setup(blackbox):
    blackbox.output = CaptureOutput()
    blackbox.formatter = Formatter()
    blackbox.formatter.set_output(blackbox.output)
    blackbox.translator = Translator()
    blackbox.translator.set_min_undo_length(100)
    blackbox.translator.add_listener(blackbox.formatter.format)
    blackbox.dictionary = blackbox.translator.get_dictionary()
    blackbox.dictionary.set_dicts([StenoDictionary()])


def blackbox_replay(blackbox, name, test):
    # Hide from traceback on assertions (reduce output size for failed tests).
    __tracebackhide__ = operator.methodcaller("errisinstance", AssertionError)
    definitions, instructions = test.strip().rsplit("\n\n", 1)
    for entry in definitions.split("\n"):
        if entry.startswith(":"):
            _blackbox_replay_action(blackbox, entry[1:])
            continue
        for steno, translation in ast.literal_eval("{" + entry + "}").items():
            blackbox.dictionary.set(normalize_steno(steno), translation)
    # Track line number for a more user-friendly assertion message.
    lines = test.split("\n")
    lnum = len(lines) - 3 - test.rstrip().rsplit("\n\n", 1)[1].count("\n")
    for step in re.split("(?<=[^\\\\])\n", instructions):
        # Mark current instruction's line.
        lnum += 1
        step = step.strip()
        # Support for changing some settings on the fly.
        if step.startswith(":"):
            _blackbox_replay_action(blackbox, step[1:])
            continue
        steno, output = step.split(None, 1)
        steno = list(map(steno_to_stroke, normalize_steno(steno.strip())))
        output = output.strip()
        assert_msg = (
            name
            + "\n"
            + "\n".join(
                ("> " if n == lnum else "  ") + line for n, line in enumerate(lines)
            )
            + "\n"
        )
        if BLACKBOX_OUTPUT_RX.match(output):
            # Replay strokes.
            list(map(blackbox.translator.translate, steno))
            # Check output.
            expected_output = ast.literal_eval(output)
            assert_msg += (
                "   " + repr(blackbox.output.text) + "\n!= " + repr(expected_output)
            )
            assert blackbox.output.text == expected_output, assert_msg
        elif output.startswith("raise "):
            expected_exception = output[6:].strip()
            try:
                list(map(blackbox.translator.translate, steno))
            except Exception as e:
                exception_class = e.__class__.__name__
            else:
                exception_class = "None"
            assert_msg += "   " + exception_class + "\n!= " + expected_exception
            assert exception_class == expected_exception, assert_msg
        else:
            raise ValueError("invalid output:\n%s" % output)


def _blackbox_replay_action(blackbox, action_spec):
    action, *args = shlex.split(action_spec)
    if action == "start_attached":
        assert not args
        blackbox.formatter.start_attached = True
    elif action == "spaces_after":
        assert not args
        blackbox.formatter.set_space_placement("After Output")
    elif action == "spaces_before":
        assert not args
        blackbox.formatter.set_space_placement("Before Output")
    elif action == "system":
        assert len(args) == 1
        system.setup(args[0])
    else:
        raise ValueError("invalid action:\n%r" % action_spec)


def blackbox_test(cls_or_fn):
    # If a class is decorated, we wrap all its test_ methods.
    if inspect.isclass(cls_or_fn):
        # Create a subclass to avoid modifying the original class
        class WrapperClass(cls_or_fn):
            pass

        # Iterate over all attributes in the class.
        for name in dir(WrapperClass):
            # Only wrap methods whose name starts with "test_"
            if name.startswith("test_"):
                fn = getattr(WrapperClass, name)
                # Recursively apply the decorator to each test function.
                new_fn = blackbox_test(fn)
                setattr(WrapperClass, name, new_fn)
        # Return the wrappped class
        return WrapperClass

    else:
        # For a single test function:
        name = cls_or_fn.__name__
        # Dedent the function's docstring which contains the blackbox test script.
        test = textwrap.dedent(cls_or_fn.__doc__)

        @functools.wraps(cls_or_fn)
        def wrapper(bb, *args, **kwargs):
            # Set up the blackbox environment:
            # - This initializes the output capture, formatter, translator,
            #   and dictionary used for replaying strokes.
            blackbox_setup(bb)
            # Execute the original test function.
            cls_or_fn(bb, *args, **kwargs)
            # Replay the test instructions captured in the dedented docstring.
            # This verifies that the outputs match what is expected.
            blackbox_replay(bb, name, test)

        # Return the wrapper function that runs setup, the test, and replay.
        return wrapper
