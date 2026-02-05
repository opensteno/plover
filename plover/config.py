# Copyright (c) 2010-2011 Joshua Harlan Lifton.
# See LICENSE.txt for details.

"""This modules handles reading and writing Plover's configuration files, as well
as updating the configuration on-the-fly while Plover is running."""

from collections import ChainMap, namedtuple, OrderedDict
import configparser
import json
import re
from typing import Any, Dict

from plover.exception import InvalidConfigurationError
from plover.machine.keymap import Keymap
from plover.registry import registry
from plover.resource import resource_update
from plover.misc import boolean, expand_path, shorten_path
from plover import log


# General configuration sections, options and defaults.
APPEARANCE_CONFIG_SECTION = "Appearance"
MACHINE_CONFIG_SECTION = "Machine Configuration"

LEGACY_DICTIONARY_CONFIG_SECTION = "Dictionary Configuration"

LOGGING_CONFIG_SECTION = "Logging Configuration"

OUTPUT_CONFIG_SECTION = "Output Configuration"
DEFAULT_UNDO_LEVELS = 100
MINIMUM_UNDO_LEVELS = 1
DEFAULT_TIME_BETWEEN_KEY_PRESSES = 0
MINIMUM_TIME_BETWEEN_KEY_PRESSES = 0

DEFAULT_SYSTEM_NAME = "English Stenotype"

SYSTEM_CONFIG_SECTION = "System: %s"
SYSTEM_KEYMAP_OPTION = "keymap[%s]"


class DictionaryConfig(namedtuple("DictionaryConfig", "path enabled")):
    """Represents the configuration for one dictionary.

    Attributes:
        path (str): The fully qualified path to the dictionary file.
        enabled (bool): Whether the dictionary is enabled.
    """

    def __new__(cls, path, enabled=True):
        return super().__new__(cls, expand_path(path), enabled)

    @property
    def short_path(self) -> str:
        """The shortened path to the dictionary file. This is automatically calculated from :attr:`path`."""
        return shorten_path(self.path)

    def to_dict(self) -> Dict[str, Any]:
        """Returns the ``dict`` representation of the dictionary configuration."""
        # Note: do not use _asdict because of
        # https://bugs.python.org/issue24931
        return {
            "path": self.short_path,
            "enabled": self.enabled,
        }

    def replace(self, **kwargs) -> "DictionaryConfig":
        """Replaces the values of :attr:`path` and :attr:`enabled` with those in ``kwargs``."""
        return self._replace(**kwargs)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "DictionaryConfig":
        """Returns a :class:`DictionaryConfig` constructed from its ``dict`` representation."""
        return DictionaryConfig(**d)

    def __repr__(self):
        return "DictionaryConfig(%r, %r)" % (self.short_path, self.enabled)


ConfigOption = namedtuple(
    "ConfigOption",
    """
                          name default
                          getter setter
                          validate full_key
                          """,
)


class InvalidConfigOption(ValueError):
    """An exception raised when a configuration option has been set to an invalid
    value, such as one of the wrong type. ``fixed_value`` is the value that
    Plover is falling back on if ``raw_value`` can't be parsed correctly.
    """

    def __init__(self, raw_value, fixed_value, message=None):
        super().__init__(raw_value)
        self.raw_value = raw_value
        self.fixed_value = fixed_value
        self.message = message

    def __str__(self):
        return self.message or repr(self.raw_value)


def raw_option(name, default, section, option, validate):
    option = option or name

    def getter(config, key):
        return config._config[section][option]

    def setter(config, key, value):
        config._set(section, option, value)

    return ConfigOption(name, lambda c, k: default, getter, setter, validate, None)


def json_option(name, default, section, option, validate):
    option = option or name

    def getter(config, key):
        value = config._config[section][option]
        try:
            return json.loads(value)
        except json.JSONDecodeError as e:
            raise InvalidConfigOption(value, default) from e

    def setter(config, key, value):
        if isinstance(value, set):
            # JSON does not support sets.
            value = list(sorted(value))
        config._set(
            section, option, json.dumps(value, sort_keys=True, ensure_ascii=False)
        )

    return ConfigOption(name, default, getter, setter, validate, None)


def int_option(name, default, minimum, maximum, section, option=None):
    option = option or name

    def getter(config, key):
        return config._config[section][option]

    def setter(config, key, value):
        config._set(section, option, str(value))

    def validate(config, key, value):
        try:
            value = int(value)
        except ValueError as e:
            raise InvalidConfigOption(value, default) from e
        if (minimum is not None and value < minimum) or (
            maximum is not None and value > maximum
        ):
            message = "%s not in [%s, %s]" % (value, minimum or "-∞", maximum or "∞")
            raise InvalidConfigOption(value, default, message)
        return value

    return ConfigOption(name, lambda c, k: default, getter, setter, validate, None)


def boolean_option(name, default, section, option=None):
    option = option or name

    def getter(config, key):
        return config._config[section][option]

    def setter(config, key, value):
        config._set(section, option, str(value))

    def validate(config, key, value):
        try:
            return boolean(value)
        except ValueError as e:
            raise InvalidConfigOption(value, default) from e

    return ConfigOption(name, lambda c, k: default, getter, setter, validate, None)


def choice_option(name, choices, section, option=None):
    default = choices[0]

    def validate(config, key, value):
        if value not in choices:
            raise InvalidConfigOption(value, default)
        return value

    return raw_option(name, default, section, option, validate)


def plugin_option(name, plugin_type, default, section, option=None):
    def validate(config, key, value):
        try:
            return registry.get_plugin(plugin_type, value).name
        except KeyError as e:
            raise InvalidConfigOption(value, default) from e

    return raw_option(name, default, section, option, validate)


def opacity_option(name, section, option=None):
    return int_option(name, 100, 0, 100, section, option)


def path_option(name, default, section, option=None):
    option = option or name

    def getter(config, key):
        return expand_path(config._config[section][option])

    def setter(config, key, value):
        config._set(section, option, shorten_path(value))

    def validate(config, key, value):
        if not isinstance(value, str):
            raise InvalidConfigOption(value, default)
        return value

    return ConfigOption(name, lambda c, k: default, getter, setter, validate, None)


def enabled_extensions_option():
    def validate(config, key, value):
        if not isinstance(value, (list, set, tuple)):
            raise InvalidConfigOption(value, ())
        return set(value)

    return json_option(
        "enabled_extensions",
        lambda c, k: set(),
        "Plugins",
        "enabled_extensions",
        validate,
    )


def machine_specific_options():
    def full_key(config, key):
        if isinstance(key, tuple):
            assert len(key) == 2
            return key
        return (key, config["machine_type"])

    def default(config, key):
        machine_class = registry.get_plugin("machine", key[1]).obj
        return {
            name: params[0] for name, params in machine_class.get_option_info().items()
        }

    def getter(config, key):
        return config._config[key[1]]

    def setter(config, key, value):
        config._config[key[1]] = value

    def validate(config, key, raw_options):
        if not isinstance(raw_options, (dict, configparser.SectionProxy)):
            raise InvalidConfigOption(raw_options, default(config, key))
        machine_options = OrderedDict()
        invalid_options = OrderedDict()
        machine_class = registry.get_plugin("machine", key[1]).obj
        for name, params in sorted(machine_class.get_option_info().items()):
            fallback, convert = params
            try:
                raw_value = raw_options[name]
            except KeyError:
                value = fallback
            else:
                try:
                    value = convert(raw_value)
                except ValueError:
                    invalid_options[name] = raw_value
                    value = fallback
            machine_options[name] = value
        if invalid_options:
            raise InvalidConfigOption(invalid_options, machine_options)
        return machine_options

    return ConfigOption(
        "machine_specific_options", default, getter, setter, validate, full_key
    )


def system_keymap_option():
    def full_key(config, key):
        if isinstance(key, tuple):
            assert len(key) == 3
            return key
        return (key, config["system_name"], config["machine_type"])

    def location(config, key):
        return SYSTEM_CONFIG_SECTION % key[1], SYSTEM_KEYMAP_OPTION % key[2]

    def build_keymap(config, key, mappings=None):
        system = registry.get_plugin("system", key[1]).obj
        machine_class = registry.get_plugin("machine", key[2]).obj
        keymap = Keymap(
            machine_class.get_keys(), system.KEYS + machine_class.get_actions()
        )
        if mappings is None:
            mappings = system.KEYMAPS.get(key[2])
        if mappings is None:
            if machine_class.KEYMAP_MACHINE_TYPE is not None:
                # Try fallback.
                return build_keymap(
                    config, (key[0], key[1], machine_class.KEYMAP_MACHINE_TYPE)
                )
            # No fallback...
            mappings = {}
        keymap.set_mappings(mappings)
        return keymap

    def default(config, key):
        return build_keymap(config, key)

    def getter(config, key):
        section, option = location(config, key)
        return config._config[section][option]

    def setter(config, key, keymap):
        section, option = location(config, key)
        config._set(section, option, str(keymap))

    def validate(config, key, value):
        try:
            return build_keymap(config, key, value)
        except (TypeError, ValueError) as e:
            raise InvalidConfigOption(value, default(config, key)) from e

    return ConfigOption("system_keymap", default, getter, setter, validate, full_key)


def dictionaries_option():
    def full_key(config, key):
        if isinstance(key, tuple):
            assert len(key) == 2
            return key
        return (key, config["system_name"])

    def location(config, key):
        return (
            SYSTEM_CONFIG_SECTION % key[1],
            "dictionaries",
        )

    def default(config, key):
        system = registry.get_plugin("system", key[1]).obj
        return [DictionaryConfig(path) for path in system.DEFAULT_DICTIONARIES]

    def legacy_getter(config):
        options = config._config[LEGACY_DICTIONARY_CONFIG_SECTION].items()
        return [
            {"path": value}
            for name, value in reversed(sorted(options))
            if re.match(r"dictionary_file\d*$", name) is not None
        ]

    def getter(config, key):
        section, option = location(config, key)
        value = config._config.get(section, option, fallback=None)
        if value is None:
            return legacy_getter(config)
        return json.loads(value)

    def setter(config, key, dictionaries):
        section, option = location(config, key)
        config._set(
            section,
            option,
            json.dumps([d.to_dict() for d in dictionaries], sort_keys=True),
        )
        config._config.remove_section(LEGACY_DICTIONARY_CONFIG_SECTION)

    def validate(config, key, value):
        dictionaries = []
        for d in value:
            if isinstance(d, DictionaryConfig):
                pass
            elif isinstance(d, str):
                d = DictionaryConfig(d)
            else:
                d = DictionaryConfig.from_dict(d)
            dictionaries.append(d)
        return dictionaries

    return ConfigOption("dictionaries", default, getter, setter, validate, full_key)


class Config:
    """An object containing the entire Plover configuration. The config object
    maintains a cache for any changes that are made while Plover is running.
    """

    def __init__(self, path=None) -> None:
        self._config = None
        self._cache = {}
        # A convenient place for other code to store a file name.
        self.path = path
        self.clear()

    def load(self) -> None:
        """Reads and parses the configuration from the configuration file. Raises an
        :exc:`InvalidConfigurationError<plover.exception.InvalidConfigurationError>`
        if the configuration could not be parsed correctly.
        """
        self.clear()
        with open(self.path, encoding="utf-8") as fp:
            try:
                self._config.read_file(fp)
            except configparser.Error as e:
                raise InvalidConfigurationError(str(e))

    def clear(self) -> None:
        """Clears the configuration and returns to the base state."""
        self._config = configparser.RawConfigParser()
        self._cache.clear()

    def save(self) -> None:
        """Writes the current state of the configuration to the configuration file."""
        with resource_update(self.path) as temp_path:
            with open(temp_path, mode="w", encoding="utf-8") as fp:
                self._config.write(fp)

    def _set(self, section, option, value):
        if not self._config.has_section(section):
            self._config.add_section(section)
        self._config.set(section, option, value)

    # Note: order matters, e.g. machine_type comes before
    # machine_specific_options and system_keymap because
    # the latter depend on the former.
    _OPTIONS = OrderedDict(
        (opt.name, opt)
        for opt in [
            # Output.
            choice_option(
                "space_placement",
                ("Before Output", "After Output"),
                OUTPUT_CONFIG_SECTION,
            ),
            boolean_option("start_attached", False, OUTPUT_CONFIG_SECTION),
            boolean_option("start_capitalized", False, OUTPUT_CONFIG_SECTION),
            int_option(
                "undo_levels",
                DEFAULT_UNDO_LEVELS,
                MINIMUM_UNDO_LEVELS,
                None,
                OUTPUT_CONFIG_SECTION,
            ),
            int_option(
                "time_between_key_presses",
                DEFAULT_TIME_BETWEEN_KEY_PRESSES,
                MINIMUM_TIME_BETWEEN_KEY_PRESSES,
                None,
                OUTPUT_CONFIG_SECTION,
            ),
            choice_option(
                "keyboard_layout",
                ("qwerty", "qwertz", "colemak", "colemak-dh", "dvorak", "wayland-auto"),
                OUTPUT_CONFIG_SECTION,
            ),
            # Logging.
            path_option(
                "log_file_name",
                expand_path("strokes.log"),
                LOGGING_CONFIG_SECTION,
                "log_file",
            ),
            boolean_option("enable_stroke_logging", False, LOGGING_CONFIG_SECTION),
            boolean_option("enable_translation_logging", False, LOGGING_CONFIG_SECTION),
            # Appearance.
            choice_option(
                "appearance_mode",
                ("system", "light", "dark"),
                APPEARANCE_CONFIG_SECTION,
                "mode",
            ),
            # GUI.
            boolean_option("start_minimized", False, "Startup", "Start Minimized"),
            boolean_option("show_stroke_display", False, "Stroke Display", "show"),
            boolean_option(
                "show_suggestions_display", False, "Suggestions Display", "show"
            ),
            opacity_option("translation_frame_opacity", "Translation Frame", "opacity"),
            boolean_option("classic_dictionaries_display_order", False, "GUI"),
            # Plugins.
            enabled_extensions_option(),
            # Machine.
            boolean_option("auto_start", False, MACHINE_CONFIG_SECTION),
            plugin_option(
                "machine_type", "machine", "Keyboard", MACHINE_CONFIG_SECTION
            ),
            machine_specific_options(),
            # System.
            plugin_option(
                "system_name", "system", DEFAULT_SYSTEM_NAME, "System", "name"
            ),
            system_keymap_option(),
            dictionaries_option(),
        ]
    )

    def _lookup(self, key):
        name = key[0] if isinstance(key, tuple) else key
        opt = self._OPTIONS[name]
        if opt.full_key is not None:
            key = opt.full_key(self, key)
        return key, opt

    def __getitem__(self, key: str) -> Any:
        """Returns the value of the specified ``key`` in the cache, or in the
        full configuration if not available.
        """
        key, opt = self._lookup(key)
        if key in self._cache:
            return self._cache[key]
        try:
            value = opt.validate(self, key, opt.getter(self, key))
        except (configparser.NoOptionError, KeyError):
            value = opt.default(self, key)
        except InvalidConfigOption as e:
            log.error("invalid value for %r option", opt.name, exc_info=True)
            value = e.fixed_value
        self._cache[key] = value
        return value

    def __setitem__(self, key: str, value: Any) -> None:
        """Sets the property ``key`` in the configuration to the specified value."""
        key, opt = self._lookup(key)
        value = opt.validate(self._config, key, value)
        opt.setter(self, key, value)
        self._cache[key] = value

    def as_dict(self) -> Dict[str, Any]:
        """Returns the ``dict`` representation of the current state of the
        configuration.
        """
        return {opt.name: self[opt.name] for opt in self._OPTIONS.values()}

    def update(self, **kwargs) -> None:
        """Update the cache to reflect the contents of the full configuration."""
        new_settings = []
        new_config = ChainMap({}, self)
        for opt in self._OPTIONS.values():
            if opt.name in kwargs:
                key = opt.name
                if opt.full_key is not None:
                    key = opt.full_key(new_config, key)
                value = opt.validate(new_config, key, kwargs[opt.name])
                new_settings.append((opt, key, value))
                new_config[opt.name] = value
        for opt, key, value in new_settings:
            opt.setter(self, key, value)
            self._cache[key] = value
