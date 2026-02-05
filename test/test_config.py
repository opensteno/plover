# Copyright (c) 2013 Hesky Fisher
# See LICENSE.txt for details.

"""Unit tests for config.py."""

from ast import literal_eval
from contextlib import ExitStack
from pathlib import Path
from site import USER_BASE
from string import Template
import inspect
import json
import os
import subprocess
import sys
import textwrap

import appdirs
import pytest

from plover import config
from plover.config import DictionaryConfig
from plover.oslayer.config import PLATFORM
from plover.machine.keyboard import Keyboard
from plover.machine.keymap import Keymap
from plover.misc import expand_path
from plover.registry import Registry
from plover.system import english_stenotype


def dedent_strip(s):
    return textwrap.dedent(s).strip()


def dict_replace(d, update):
    d = dict(d)
    d.update(update)
    return d


class FakeMachine:
    KEYMAP_MACHINE_TYPE = "Keyboard"

    def get_keys():
        return Keyboard.get_keys()

    def get_actions():
        return Keyboard.get_actions()

    @staticmethod
    def get_option_info():
        def bool_converter(s):
            return s == "True"

        return {
            "stroption1": (None, str),
            "intoption1": (3, int),
            "stroption2": ("abc", str),
            "floatoption1": (1, float),
            "booloption1": (True, bool_converter),
            "booloption2": (False, bool_converter),
        }


FakeMachine.DEFAULT_OPTIONS = {
    k: v[0] for k, v in FakeMachine.get_option_info().items()
}


class FakeSystem:
    KEYS = english_stenotype.KEYS
    IMPLICIT_HYPHEN_KEYS = ()
    SUFFIX_KEYS = ()
    NUMBER_KEY = english_stenotype.NUMBER_KEY
    NUMBERS = english_stenotype.NUMBERS
    UNDO_STROKE_STENO = english_stenotype.UNDO_STROKE_STENO
    ORTHOGRAPHY_RULES = []
    ORTHOGRAPHY_RULES_ALIASES = {}
    ORTHOGRAPHY_WORDLIST = None
    KEYMAPS = {
        "Faky faky": english_stenotype.KEYMAPS["Keyboard"],
    }
    DEFAULT_DICTIONARIES = ("utilisateur.json", "principal.json")


def test_config_dict():
    short_path = os.path.normcase(os.path.normpath("~/foo/bar"))
    full_path = os.path.normcase(os.path.expanduser(os.path.normpath("~/foo/bar")))
    # Path should be expanded.
    assert DictionaryConfig(short_path).path == full_path
    assert DictionaryConfig(full_path).path == full_path
    # Short path is available through `short_path`.
    assert DictionaryConfig(full_path).short_path == short_path
    assert DictionaryConfig(short_path).short_path == short_path
    # Enabled default to True.
    assert DictionaryConfig("foo").enabled
    assert not DictionaryConfig("foo", False).enabled
    # When converting to a dict (for dumping to JSON),
    # a dictionary with the shortened path is used.
    assert DictionaryConfig(full_path).to_dict() == {
        "path": short_path,
        "enabled": True,
    }
    assert DictionaryConfig(short_path, False).to_dict() == {
        "path": short_path,
        "enabled": False,
    }
    # Test from_dict creation helper.
    assert DictionaryConfig.from_dict({"path": short_path}) == DictionaryConfig(
        short_path
    )
    assert DictionaryConfig.from_dict(
        {"path": full_path, "enabled": False}
    ) == DictionaryConfig(short_path, False)


if PLATFORM == "win":
    ABS_PATH = os.path.normcase(r"c:/foo/bar")
else:
    ABS_PATH = "/foo/bar"

DEFAULT_KEYMAP = Keymap(
    Keyboard.get_keys(), english_stenotype.KEYS + Keyboard.get_actions()
)
DEFAULT_KEYMAP.set_mappings(english_stenotype.KEYMAPS["Keyboard"])

DEFAULTS = {
    "space_placement": "Before Output",
    "start_attached": False,
    "start_capitalized": False,
    "undo_levels": config.DEFAULT_UNDO_LEVELS,
    "log_file_name": expand_path("strokes.log"),
    "enable_stroke_logging": False,
    "enable_translation_logging": False,
    "start_minimized": False,
    "show_stroke_display": False,
    "show_suggestions_display": False,
    "translation_frame_opacity": 100,
    "classic_dictionaries_display_order": False,
    "enabled_extensions": set(),
    "auto_start": False,
    "machine_type": "Keyboard",
    "machine_specific_options": {"arpeggiate": False, "first_up_chord_send": False},
    "system_name": config.DEFAULT_SYSTEM_NAME,
    "system_keymap": DEFAULT_KEYMAP,
    "dictionaries": [
        DictionaryConfig(p) for p in english_stenotype.DEFAULT_DICTIONARIES
    ],
}

CONFIG_TESTS = (
    (
        "defaults",
        """
     """,
        DEFAULTS,
        {},
        {},
        """
     """,
    ),
    (
        "simple_options",
        """
     [Output Configuration]
     space_placement = After Output
     start_attached = true
     start_capitalized = yes
     undo_levels = 42
     """,
        dict_replace(
            DEFAULTS,
            {
                "space_placement": "After Output",
                "start_attached": True,
                "start_capitalized": True,
                "undo_levels": 42,
            },
        ),
        {
            "space_placement": "Before Output",
            "start_attached": False,
            "start_capitalized": False,
            "undo_levels": 200,
        },
        None,
        """
     [Output Configuration]
     space_placement = Before Output
     start_attached = False
     start_capitalized = False
     undo_levels = 200
     """,
    ),
    (
        "machine_options",
        """
     [Machine Configuration]
     auto_start = True
     machine_type = keyboard

     [Keyboard]
     arpeggiate = True
     """,
        dict_replace(
            DEFAULTS,
            {
                "auto_start": True,
                "machine_specific_options": dict_replace(
                    DEFAULTS["machine_specific_options"],
                    {
                        "arpeggiate": True,
                    },
                ),
            },
        ),
        {
            "machine_type": "faKY FAky",
            "machine_specific_options": {
                "stroption1": 42,
                "floatoption1": "4.2",
                "booloption1": False,
            },
            "system_name": "FAUX SYSTÈME",
            "system_keymap": str(DEFAULT_KEYMAP),
        },
        {
            "machine_type": "Faky faky",
            "machine_specific_options": dict_replace(
                FakeMachine.DEFAULT_OPTIONS,
                {
                    "stroption1": "42",
                    "floatoption1": 4.2,
                    "booloption1": False,
                },
            ),
            "system_name": "Faux système",
            "system_keymap": DEFAULT_KEYMAP,
            "dictionaries": [
                DictionaryConfig("utilisateur.json"),
                DictionaryConfig("principal.json"),
            ],
        },
        """
     [Machine Configuration]
     auto_start = True
     machine_type = Faky faky

     [Keyboard]
     arpeggiate = True

     [Faky faky]
     booloption1 = False
     booloption2 = False
     floatoption1 = 4.2
     intoption1 = 3
     stroption1 = 42
     stroption2 = abc

     [System]
     name = Faux système

     [System: Faux système]
     keymap[faky faky] = %s
     """
        % DEFAULT_KEYMAP,
    ),
    (
        "machine_bool_option",
        """
     """,
        DEFAULTS,
        {
            "machine_specific_options": {
                "arpeggiate": True,
            },
        },
        {
            "machine_specific_options": {
                "arpeggiate": True,
                "first_up_chord_send": False,
            }
        },
        """
     [Keyboard]
     arpeggiate = True
     first_up_chord_send = False
     """,
    ),
    (
        "legacy_dictionaries_1",
        """
     [Dictionary Configuration]
     dictionary_file = main.json
     """,
        dict_replace(
            DEFAULTS,
            {
                "dictionaries": [DictionaryConfig("main.json")],
            },
        ),
        {
            "dictionaries": ["user.json", "main.json"],
        },
        {
            "dictionaries": [
                DictionaryConfig("user.json"),
                DictionaryConfig("main.json"),
            ],
        },
        """
     [System: English Stenotype]
     dictionaries = [{"enabled": true, "path": "user.json"}, {"enabled": true, "path": "main.json"}]
     """,
    ),
    (
        "legacy_dictionaries_2",
        """
     [Dictionary Configuration]
     dictionary_file1 = main.json
     dictionary_file3 = user.json
     """,
        dict_replace(
            DEFAULTS,
            {
                "dictionaries": [
                    DictionaryConfig("user.json"),
                    DictionaryConfig("main.json"),
                ],
            },
        ),
        {
            "dictionaries": ["user.json", "commands.json", "main.json"],
        },
        {
            "dictionaries": [
                DictionaryConfig("user.json"),
                DictionaryConfig("commands.json"),
                DictionaryConfig("main.json"),
            ],
        },
        """
     [System: English Stenotype]
     dictionaries = [{"enabled": true, "path": "user.json"}, {"enabled": true, "path": "commands.json"}, {"enabled": true, "path": "main.json"}]
     """,
    ),
    (
        "dictionaries",
        """
     [System: English Stenotype]
     dictionaries = %s
     """
        % json.dumps([os.path.join(ABS_PATH, "user.json"), "english/main.json"]),
        dict_replace(
            DEFAULTS,
            {
                "dictionaries": [
                    DictionaryConfig(os.path.join(ABS_PATH, "user.json")),
                    DictionaryConfig("english/main.json"),
                ],
            },
        ),
        {
            "dictionaries": [
                DictionaryConfig(os.path.join(ABS_PATH, "user.json")),
                DictionaryConfig("english/main.json"),
            ],
        },
        {
            "dictionaries": [
                DictionaryConfig(os.path.join(ABS_PATH, "user.json")),
                DictionaryConfig("english/main.json"),
            ],
        },
        """
     [System: English Stenotype]
     dictionaries = %s
     """
        % json.dumps(
            [
                {"enabled": True, "path": os.path.join(ABS_PATH, "user.json")},
                {"enabled": True, "path": os.path.join("english", "main.json")},
            ],
            sort_keys=True,
        ),
    ),
    (
        "invalid_config",
        """
     [Startup]
     Start Minimized = True

     [Machine Configuratio
     machine_type = Faky faky
     """,
        config.InvalidConfigurationError,
        {},
        {},
        """
     """,
    ),
    (
        "invalid_keymap_1",
        """
     [System: English Stenotype]
     keymap[keyboard] = [["_-"]]
     """,
        DEFAULTS,
        {},
        {},
        None,
    ),
    (
        "invalid_keymap_2",
        """
     [System: English Stenotype]
     keymap[keyboard] = 42
     """,
        DEFAULTS,
        {},
        {},
        None,
    ),
    (
        "invalid_options_1",
        """
     [System]
     name = foobar
     """,
        DEFAULTS,
        {},
        {},
        None,
    ),
    (
        "invalid_options_2",
        """
     [Machine Configuration]
     machine_type = Faky faky

     [Faky faky]
     booloption2 = 50
     intoption1 = 3.14
     """,
        dict_replace(
            DEFAULTS,
            {
                "machine_type": "Faky faky",
                "machine_specific_options": FakeMachine.DEFAULT_OPTIONS,
            },
        ),
        {},
        {},
        None,
    ),
    (
        "invalid_options_3",
        """
     [Output Configuration]
     undo_levels = foobar
     """,
        DEFAULTS,
        {},
        {},
        None,
    ),
    (
        "invalid_update_1",
        """
     [Translation Frame]
     opacity = 75
     """,
        dict_replace(
            DEFAULTS,
            {
                "translation_frame_opacity": 75,
            },
        ),
        {
            "start_minimized": False,
            "show_stroke_display": True,
            "translation_frame_opacity": 101,
        },
        config.InvalidConfigOption,
        None,
    ),
    (
        "invalid_update_2",
        """
     """,
        DEFAULTS,
        {
            "machine_type": "FakeMachine",
            "machine_specific_options": dict_replace(
                FakeMachine.DEFAULT_OPTIONS,
                {
                    "stroption1": "42",
                },
            ),
        },
        config.InvalidConfigOption,
        None,
    ),
    (
        "setitem_valid",
        """
     """,
        DEFAULTS,
        ("auto_start", True),
        None,
        """
     [Machine Configuration]
     auto_start = True
     """,
    ),
    (
        "setitem_invalid",
        """
     """,
        DEFAULTS,
        ("undo_levels", -42),
        config.InvalidConfigOption,
        """
     """,
    ),
)


@pytest.mark.parametrize(
    (
        "original_contents",
        "original_config",
        "config_update",
        "validated_config_update",
        "resulting_contents",
    ),
    [t[1:] for t in CONFIG_TESTS],
    ids=[t[0] for t in CONFIG_TESTS],
)
def test_config(
    original_contents,
    original_config,
    config_update,
    validated_config_update,
    resulting_contents,
    monkeypatch,
    tmpdir,
):
    registry = Registry()
    registry.register_plugin("machine", "Keyboard", Keyboard)
    registry.register_plugin("machine", "Faky faky", FakeMachine)
    registry.register_plugin("system", "English Stenotype", english_stenotype)
    registry.register_plugin("system", "Faux système", FakeSystem)
    monkeypatch.setattr("plover.config.registry", registry)
    config_file = tmpdir / "config.cfg"
    # Check initial contents.
    config_file.write_text(original_contents, encoding="utf-8")
    cfg = config.Config(config_file.strpath)
    if inspect.isclass(original_config):
        with pytest.raises(original_config):
            cfg.load()
        original_config = dict(DEFAULTS)
        cfg.clear()
    else:
        cfg.load()
    cfg_dict = cfg.as_dict()
    for name, value in original_config.items():
        assert cfg[name] == value
        assert cfg_dict[name] == value
    # Check updated contents.
    with ExitStack() as stack:
        if inspect.isclass(validated_config_update):
            stack.enter_context(pytest.raises(validated_config_update))
            validated_config_update = None
        elif validated_config_update is None:
            validated_config_update = config_update
        if isinstance(config_update, dict):
            cfg.update(**config_update)
        else:
            key, value = config_update
            cfg[key] = value
        if validated_config_update is not None:
            if isinstance(validated_config_update, dict):
                cfg_dict.update(validated_config_update)
            else:
                key, value = validated_config_update
                cfg_dict[key] = value
        assert cfg.as_dict() == cfg_dict
    config_file.write_text("", encoding="utf-8")
    cfg.save()
    if resulting_contents is None:
        resulting_contents = original_contents
    assert config_file.read_text(encoding="utf-8").strip() == dedent_strip(
        resulting_contents
    )


CONFIG_MISSING_INTS_TESTS = (
    (
        "int_option",
        config.OUTPUT_CONFIG_SECTION,
        "undo_levels",
        config.DEFAULT_UNDO_LEVELS,
    ),
    (
        "opacity_option",
        "Translation Frame",
        "translation_frame_opacity",
        100,
    ),
)


@pytest.mark.parametrize(
    ("which_section", "which_option", "fixed_value"),
    [t[1:] for t in CONFIG_MISSING_INTS_TESTS],
    ids=[t[0] for t in CONFIG_MISSING_INTS_TESTS],
)
def test_config_missing_ints(
    which_section, which_option, fixed_value, monkeypatch, tmpdir, caplog
):
    registry = Registry()
    registry.register_plugin("machine", "Keyboard", Keyboard)
    registry.register_plugin("system", "English Stenotype", english_stenotype)
    monkeypatch.setattr("plover.config.registry", registry)
    config_file = tmpdir / "config.cfg"

    # Make config with the appropriate empty section
    contents = f"""
    [{which_section}]
    """
    config_file.write_text(contents, encoding="utf-8")
    cfg = config.Config(config_file.strpath)
    cfg.load()

    # Try to access an option under that section
    # (should trigger validation)
    assert cfg[which_option] == fixed_value

    # Ensure that missing options are handled
    assert "InvalidConfigOption: None" not in caplog.text
    # ... or any that there aren't any unhandled errors
    for record in caplog.records:
        assert record.levelname != "ERROR"


CONFIG_DIR_TESTS = (
    # Default to `user_config_dir`.
    (
        """
     $user_config_dir/foo.cfg
     $user_data_dir/bar.cfg
     $cwd/config.cfg
     """,
        "$user_config_dir",
    ),
    # Use cwd if config file is present, override other directories.
    (
        """
     $user_config_dir/plover.cfg
     $user_data_dir/plover.cfg
     $cwd/plover.cfg
     """,
        "$cwd",
    ),
    # plover.cfg must be a file.
    (
        """
     $user_data_dir/plover.cfg
     $cwd/plover.cfg/config
     """,
        "$user_data_dir",
    ),
)

if appdirs.user_data_dir() != appdirs.user_config_dir():
    CONFIG_DIR_TESTS += (
        # `user_config_dir` take precedence over `user_data_dir`.
        (
            """
         $user_config_dir/plover.cfg
         $user_data_dir/plover.cfg
         $cwd/config.cfg
         """,
            "$user_config_dir",
        ),
        # But `user_data_dir` is still used when applicable.
        (
            """
         $user_config_dir/plover.cfg/conf
         $user_data_dir/plover.cfg
         $cwd/config.cfg
         """,
            "$user_data_dir",
        ),
    )


@pytest.mark.parametrize(("tree", "expected_config_dir"), CONFIG_DIR_TESTS)
def test_config_dir(tree, expected_config_dir, tmpdir):
    # Create fake home/cwd directories.
    home = tmpdir / "home"
    home.mkdir()
    cwd = tmpdir / "cwd"
    cwd.mkdir()
    directories = {
        "tmpdir": str(tmpdir),
        "home": str(home),
        "cwd": str(cwd),
    }
    # Setup environment.
    env = dict(os.environ)
    if PLATFORM == "win":
        env["USERPROFILE"] = str(home)
    else:
        env["HOME"] = str(home)
    env["PYTHONUSERBASE"] = USER_BASE
    # Ensure XDG_xxx environment variables don't screw up our isolation.
    for k in list(env):
        if k.startswith("XDG_"):
            del env[k]

    # Helpers.
    def pyeval(script):
        return literal_eval(
            subprocess.check_output(
                (sys.executable, "-c", script), cwd=str(cwd), env=env
            ).decode()
        )

    def path_expand(path):
        return Template(path.replace("/", os.sep)).substitute(**directories)

    # Find out user_config_dir/user_data_dir locations.
    directories.update(
        pyeval(
            dedent_strip(
                """
        import appdirs, os
        print(repr({
            'user_config_dir': appdirs.user_config_dir('plover'),
            'user_data_dir': appdirs.user_data_dir('plover'),
        }))
        """
            )
        )
    )
    # Create initial tree.
    created_files = []
    for filename_template in dedent_strip(tree).replace("/", os.sep).split("\n"):
        filename = Path(path_expand(filename_template))
        filename.parent.mkdir(parents=True, exist_ok=True)
        filename.write_text("pouet")
        created_files.append(filename)
    # Check plover.oslayer.config.CONFIG_DIR is correctly set.
    config_dir = pyeval(
        dedent_strip(
            """
        __import__('sys').path.insert(0, %r)
        from plover.oslayer.config import CONFIG_DIR
        print(repr(CONFIG_DIR))
        """
            % str(Path(config.__file__).parent.parent)
        )
    )
    expected_config_dir = path_expand(expected_config_dir)
    assert config_dir == expected_config_dir
    # Cleanup created files and directories.
    for file in created_files:
        try:
            file.unlink()  # Delete the file
        except FileNotFoundError:
            pass
    for file in created_files:
        try:
            file.parent.rmdir()  # Attempt to remove empty directories
        except OSError:
            pass
