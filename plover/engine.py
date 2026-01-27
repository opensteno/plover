"""The steno engine is the core of Plover; it handles communication between the
machine and the translation and formatting subsystems, and manages configuration
and dictionaries.
"""

from collections import namedtuple, OrderedDict
from functools import wraps
from queue import Queue
import functools
import os
import shutil
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple

from plover import log, system
from plover.dictionary.loading_manager import DictionaryLoadingManager
from plover.formatting import Formatter
from plover.misc import shorten_path
from plover.registry import registry
from plover.resource import ASSET_SCHEME, resource_filename
from plover.steno import Stroke
from plover.steno_dictionary import StenoDictionary, StenoDictionaryCollection
from plover.suggestions import Suggestions
from plover.translation import Translator


StartingStrokeState = namedtuple(
    "StartingStrokeState", "attach capitalize space_char", defaults=(False, False, " ")
)

StartingStrokeState.__doc__ = """An object representing the starting state of the formatter before any
strokes are input.

Attributes:
    attach (bool): Whether to delete the space before the translation when the
        initial stroke is translated.
    capitalize (bool): Whether to capitalize the translation when the initial
        stroke is translated.
"""

MachineParams = namedtuple("MachineParams", "type options keymap")

MachineParams.__doc__ = """An object representing the current state of the machine.

Attributes:
    type (str): The name of the machine. This is the same as the name of the plugin
        that provides the machine's functionality. ``Keyboard`` by default.
    options (Dict[str, Any]): A dictionary of machine specific options. See
        :mod:`plover.config` for more information.
    keymap (plover.machine.keymap.Keymap): A
        :class:`Keymap<plover.machine.keymap.Keymap>` mapping the current
        system to this machine.
"""


class ErroredDictionary(StenoDictionary):
    """A placeholder class for a dictionary that failed to load.

    This is a subclass of :class:`StenoDictionary<plover.steno_dictionary.StenoDictionary>`.

    Attributes:
        path (str): The path to the dictionary file.
        exception (Any): The exception that caused the dictionary loading to fail.
    """

    def __init__(self, path: str, exception: Any):
        super().__init__()
        self.enabled = False
        self.readonly = True
        self.path = path
        self.exception = exception

    def __eq__(self, other):
        if not isinstance(other, ErroredDictionary):
            return False
        return (self.path, self.exception) == (other.path, other.exception)


def copy_default_dictionaries(dictionaries_files):
    """Recreate default dictionaries.

    Each default dictionary is recreated if it's
    in use by the current config and missing.
    """

    for dictionary in dictionaries_files:
        # Ignore assets.
        if dictionary.startswith(ASSET_SCHEME):
            continue
        # Nothing to do if dictionary file already exists.
        if os.path.exists(dictionary):
            continue
        # Check it's actually a default dictionary.
        basename = os.path.basename(dictionary)
        if basename not in system.DEFAULT_DICTIONARIES:
            continue
        default_dictionary = os.path.join(system.DICTIONARIES_ROOT, basename)
        log.info("recreating %s from %s", dictionary, default_dictionary)
        shutil.copyfile(resource_filename(default_dictionary), dictionary)


def with_lock(func):
    # To keep __doc__/__name__ attributes of the initial function.
    @wraps(func)
    def _with_lock(self, *args, **kwargs):
        with self:
            return func(self, *args, **kwargs)

    return _with_lock


class StenoEngine:
    """
    Attributes:
        config (Dict[str, Any]): A dictionary containing configuration options.
        controller (plover.oslayer.controller.Controller): An instance of
            :class:`Controller<plover.oslayer.controller.Controller>` for managing
            commands sent to this Plover instance. This is provided during startup.
        keyboard_emulation (plover.oslayer.keyboardcontrol.KeyboardEmulation): An
            instance of
            :class:`KeyboardEmulation<plover.oslayer.keyboardcontrol.KeyboardEmulation>`
            provided during startup.
        HOOKS (List[str]): A list of all the possible engine hooks. See
            :ref:`engine-hooks` below for a list of valid hooks.
        machine_state (str): The connection state of the current machine. One of
            ``stopped``, ``initializing``, ``connected`` or ``disconnected``.
        output (bool): ``True`` if steno output is enabled, ``False`` otherwise.
        _config (plover.config.Config): A :class:`Config<plover.config.Config>` object
            containing the engine's configuration.
        translator_state (plover.translation._State): A
            :class:`_State<plover.translation._State>` object containing the current
            state of the translator.
        starting_stroke_state (StartingStrokeState): A :class:`StartingStrokeState`
            representing the initial state of the formatter.
        dictionaries (plover.steno_dictionary.StenoDictionaryCollection): A
            :class:`StenoDictionaryCollection<plover.steno_dictionary.StenoDictionaryCollection>`
            of all the dictionaries Plover has loaded for the current system. This
            includes disabled dictionaries and dictionaries that failed to load.

    """

    HOOKS: List[str] = """
    stroked
    translated
    machine_state_changed
    output_changed
    config_changed
    dictionaries_loaded
    dictionary_state_changed
    send_string
    send_backspaces
    send_key_combination
    add_translation
    focus
    configure
    lookup
    suggestions
    quit
    """.split()

    def __init__(self, config: Any, controller: Any, keyboard_emulation: Any):
        self._config = config
        self._controller = controller
        self._is_running = False
        self._queue = Queue()
        self._lock = threading.RLock()
        self._machine = None
        self._machine_state = None
        self._machine_params = MachineParams(None, None, None)
        self._formatter = Formatter()
        self._formatter.set_output(
            Formatter.output_type(
                self._send_backspaces,
                self._send_string,
                self._send_key_combination,
                self._send_engine_command,
            )
        )
        self._formatter.add_listener(self._on_translated)
        self._translator = Translator()
        self._translator.add_listener(log.translation)
        self._translator.add_listener(self._formatter.format)
        self._dictionaries = self._translator.get_dictionary()  # type: StenoDictionaryCollection
        self._dictionaries_manager = DictionaryLoadingManager(
            functools.partial(self._trigger_hook, "dictionary_state_changed")
        )
        self._running_state = self._translator.get_state()
        self._translator.clear_state()
        self._keyboard_emulation = keyboard_emulation
        self._hooks = {hook: [] for hook in self.HOOKS}
        self._running_extensions = {}

    def __enter__(self):
        self._lock.__enter__()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._lock.__exit__(exc_type, exc_value, traceback)

    def _in_engine_thread(self) -> bool:
        """Returns whether we are currently in the same thread that the engine
        is running on.

        This is useful because event listeners for machines and others are run
        on separate threads, and we want to be able to run engine events on the
        same thread as the main engine.
        """
        raise NotImplementedError()

    def _same_thread_hook(self, func, *args, **kwargs):
        if self._in_engine_thread():
            func(*args, **kwargs)
        else:
            self._queue.put((func, args, kwargs))

    def run(self) -> None:
        """Starts the steno engine, translating any strokes that are input."""
        while True:
            func, args, kwargs = self._queue.get()
            try:
                with self._lock:
                    if func(*args, **kwargs):
                        break
            except Exception:
                log.error("engine %s failed", func.__name__[1:], exc_info=True)

    def _on_control_message(self, msg):
        if msg[0] == "command":
            self._same_thread_hook(self._execute_engine_command, *msg[1:], force=True)
        else:
            log.error("ignoring invalid control message: %r", msg)

    def _stop(self):
        self._controller.stop()
        self._stop_extensions(self._running_extensions.keys())
        if self._machine is not None:
            self._machine.stop_capture()
            self._machine = None

    def _start(self):
        self._set_output(self._config["auto_start"])
        self._update(full=True)
        self._controller.start(self._on_control_message)

    def _set_dictionaries(self, dictionaries):
        def dictionaries_changed(l1, l2):
            if len(l1) != len(l2):
                return True
            for d1, d2 in zip(l1, l2):
                if d1 is not d2:
                    return True
            return False

        if not dictionaries_changed(dictionaries, self._dictionaries.dicts):
            # No change.
            return
        self._dictionaries.set_dicts(dictionaries)
        self._trigger_hook(
            "dictionaries_loaded", StenoDictionaryCollection(dictionaries)
        )

    def _update(self, config_update=None, full=False, reset_machine=False):
        original_config = self._config.as_dict()
        # Update configuration.
        if config_update is not None:
            self._config.update(**config_update)
            config = self._config.as_dict()
        else:
            config = original_config
        # Create configuration update.
        if full:
            config_update = config
        else:
            config_update = {
                option: value
                for option, value in config.items()
                if value != original_config[option]
            }
            # Save config if anything changed.
            if config_update:
                self._config.save()
        # Update logging.
        log.set_stroke_filename(config["log_file_name"])
        log.enable_stroke_logging(config["enable_stroke_logging"])
        log.enable_translation_logging(config["enable_translation_logging"])
        # Update output.
        self._formatter.set_space_placement(config["space_placement"])
        self._formatter.start_attached = config["start_attached"]
        self._formatter.start_capitalized = config["start_capitalized"]
        self._translator.set_min_undo_length(config["undo_levels"])
        self._keyboard_emulation.set_key_press_delay(config["time_between_key_presses"])
        # This only applies to UInput, because it emulates a physical keyboard and follows the layout set in software. Because there is no standard of defining it, the user has to do so manually if not using a QWERTY keyboard.
        if hasattr(self._keyboard_emulation, "_update_layout"):
            self._keyboard_emulation._update_layout(config["keyboard_layout"])
        # Update system.
        system_name = config["system_name"]
        if system.NAME != system_name:
            log.info("loading system: %s", system_name)
            system.setup(system_name)
        # Update machine.
        update_keymap = False
        start_machine = False
        machine_params = MachineParams(
            config["machine_type"],
            config["machine_specific_options"],
            config["system_keymap"],
        )
        # Do not reset if only the keymap changed.
        if (
            self._machine_params is None
            or self._machine_params.type != machine_params.type
            or self._machine_params.options != machine_params.options
        ):
            reset_machine = True
        if reset_machine:
            if self._machine is not None:
                self._machine.stop_capture()
                self._machine = None
            machine_class = registry.get_plugin("machine", machine_params.type).obj
            log.info("setting machine: %s", machine_params.type)
            self._machine = machine_class(machine_params.options)
            self._machine.set_suppression(self._is_running)
            self._machine.add_state_callback(self._machine_state_callback)
            self._machine.add_stroke_callback(self._machine_stroke_callback)
            self._machine_params = machine_params
            update_keymap = True
            start_machine = True
        elif self._machine is not None:
            update_keymap = "system_keymap" in config_update
        if update_keymap:
            machine_keymap = config["system_keymap"]
            if machine_keymap is not None:
                self._machine.set_keymap(machine_keymap)
        if start_machine:
            self._machine.start_capture()
        # Update running extensions.
        enabled_extensions = config["enabled_extensions"]
        running_extensions = set(self._running_extensions)
        self._stop_extensions(running_extensions - enabled_extensions)
        self._start_extensions(enabled_extensions - running_extensions)
        # Trigger `config_changed` hook.
        if config_update:
            self._trigger_hook("config_changed", config_update)
        # Update dictionaries.
        config_dictionaries = OrderedDict((d.path, d) for d in config["dictionaries"])
        copy_default_dictionaries(config_dictionaries.keys())
        # Start by unloading outdated dictionaries.
        self._dictionaries_manager.unload_outdated()
        self._set_dictionaries(
            [
                d
                for d in self._dictionaries.dicts
                if d.path in config_dictionaries
                and d.path in self._dictionaries_manager
            ]
        )
        # And then (re)load all dictionaries.
        dictionaries = []
        for d in self._dictionaries_manager.load(config_dictionaries.keys()):
            if isinstance(d, ErroredDictionary):
                # Only show an error if it's new.
                if d != self._dictionaries.get(d.path):
                    log.error(
                        "loading dictionary `%s` failed: %s",
                        shorten_path(d.path),
                        str(d.exception),
                    )
            d.enabled = config_dictionaries[d.path].enabled
            dictionaries.append(d)
        self._set_dictionaries(dictionaries)

    def _start_extensions(self, extension_list):
        for extension_name in extension_list:
            log.info("starting `%s` extension", extension_name)
            try:
                extension = registry.get_plugin("extension", extension_name).obj(self)
            except KeyError:
                # Plugin not installed, skip.
                continue
            try:
                extension.start()
            except Exception:
                log.error(
                    "initializing extension `%s` failed", extension_name, exc_info=True
                )
            else:
                self._running_extensions[extension_name] = extension

    def _stop_extensions(self, extension_list):
        for extension_name in list(extension_list):
            log.info("stopping `%s` extension", extension_name)
            extension = self._running_extensions.pop(extension_name)
            extension.stop()
            del extension

    def _quit(self, code):
        self._stop()
        self.code = code
        self._trigger_hook("quit")
        return True

    def _toggle_output(self):
        self._set_output(not self._is_running)

    def _set_output(self, enabled):
        if enabled == self._is_running:
            return
        self._is_running = enabled
        if enabled:
            self._translator.set_state(self._running_state)
        else:
            self._translator.clear_state()
        if self._machine is not None:
            self._machine.set_suppression(enabled)
        self._trigger_hook("output_changed", enabled)

    def _machine_state_callback(self, machine_state):
        self._same_thread_hook(self._on_machine_state_changed, machine_state)

    def _machine_stroke_callback(self, steno_keys):
        self._same_thread_hook(self._on_stroked, steno_keys)

    @with_lock
    def _on_machine_state_changed(self, machine_state):
        assert machine_state is not None
        self._machine_state = machine_state
        self._trigger_hook(
            "machine_state_changed", self._machine_params.type, machine_state
        )

    def _consume_engine_command(self, command, force=False):
        # The first commands can be used whether plover has output enabled or not.
        command_name, *command_args = command.split(":", 1)
        command_name = command_name.lower()
        if command_name == "resume":
            self._set_output(True)
            return True
        elif command_name == "toggle":
            self._toggle_output()
            return True
        elif command_name == "quit":
            self.quit()
            return True
        if not force and not self._is_running:
            return False
        # These commands can only be run when plover has output enabled.
        if command_name == "suspend":
            self._set_output(False)
        elif command_name == "configure":
            self._trigger_hook("configure")
        elif command_name == "focus":
            self._trigger_hook("focus")
        elif command_name == "add_translation":
            self._trigger_hook("add_translation")
        elif command_name == "lookup":
            self._trigger_hook("lookup")
        elif command_name == "suggestions":
            self._trigger_hook("suggestions")
        else:
            command_fn = registry.get_plugin("command", command_name).obj
            command_fn(self, command_args[0] if command_args else "")
        return False

    def _execute_engine_command(self, command, force=False):
        self._consume_engine_command(command, force=force)
        return False

    def _on_stroked(self, steno_keys):
        stroke = Stroke(steno_keys)
        log.stroke(stroke)
        self._translator.translate(stroke)
        self._trigger_hook("stroked", stroke)

    def _on_translated(self, old, new):
        if not self._is_running:
            return
        self._trigger_hook("translated", old, new)

    def _send_backspaces(self, b):
        if not self._is_running:
            return
        self._keyboard_emulation.send_backspaces(b)
        self._trigger_hook("send_backspaces", b)

    def _send_string(self, s):
        if not self._is_running:
            return
        self._keyboard_emulation.send_string(s)
        self._trigger_hook("send_string", s)

    def _send_key_combination(self, c):
        if not self._is_running:
            return
        self._keyboard_emulation.send_key_combination(c)
        self._trigger_hook("send_key_combination", c)

    def _send_engine_command(self, command: str) -> None:
        """Runs the specified Plover command, which can be either a built-in
        command like ``set_config`` or one from an external plugin.

        ``command`` is a string containing the command and its argument (if any),
        separated by a colon. For example, ``lookup`` sends the ``lookup`` command
        (the same as stroking ``{PLOVER:LOOKUP}``), and ``run_shell:foo`` sends the
        ``run_shell`` command with the argument ``foo``.
        """
        suppress = not self._is_running
        suppress &= self._consume_engine_command(command)
        if suppress:
            self._machine.suppress_last_stroke(self._keyboard_emulation.send_backspaces)

    def toggle_output(self):
        """Toggles steno mode.

        See :attr:`output` to get the current state, or
        :meth:`set_output` to set the state to a specific value.
        """
        self._same_thread_hook(self._toggle_output)

    def set_output(self, enabled: bool) -> None:
        """Enables or disables steno mode.

        Set ``enabled`` to ``True`` to enable steno mode, or ``False`` to disable it.
        """
        self._same_thread_hook(self._set_output, enabled)

    @property
    @with_lock
    def machine_state(self) -> Optional[str]:
        """The connection state of the current machine.

        One of ``stopped``, ``initializing``, ``connected`` or ``disconnected``.
        """
        return self._machine_state

    @property
    @with_lock
    def output(self) -> bool:
        """``True`` if steno output is enabled, ``False`` otherwise."""
        return self._is_running

    @output.setter
    def output(self, enabled):
        self._same_thread_hook(self._set_output, enabled)

    @property
    @with_lock
    def config(self) -> Dict[str, Any]:
        """A dictionary containing configuration options."""
        return self._config.as_dict()

    @config.setter
    def config(self, update):
        self._same_thread_hook(self._update, config_update=update)

    @with_lock
    def __getitem__(self, setting: str) -> Any:
        """Returns the value of the configuration property ``setting``."""
        return self._config[setting]

    def __setitem__(self, setting: str, value: Any) -> None:
        """Sets the configuration property ``setting`` to ``value``."""
        self.config = {setting: value}

    def reset_machine(self) -> None:
        """Resets the machine state and Plover's connection with the machine, if
        necessary, and loads all the configuration and dictionaries.
        """
        self._same_thread_hook(self._update, reset_machine=True)

    def load_config(self) -> bool:
        """Loads the Plover configuration file and returns ``True`` if it was
        loaded successfully, ``False`` if not.
        """
        try:
            self._config.load()
        except Exception:
            log.error(
                "loading configuration failed, resetting to default", exc_info=True
            )
            self._config.clear()
            return False
        return True

    def start(self) -> None:
        """Starts the steno engine."""
        self._same_thread_hook(self._start)

    def quit(self, code: int = 0) -> None:
        """Quits the steno engine, ensuring that all pending tasks are completed
        before exiting.
        """
        # We need to go through the queue, even when already called
        # from the engine thread so _quit's return code does break
        # the thread out of its main loop.
        self._queue.put((self._quit, (code,), {}))

    def restart(self) -> None:
        """Quits and restarts the steno engine, ensuring that all pending tasks
        are completed.
        """
        self.quit(-1)

    def join(self) -> int:
        """Joins any sub-threads if necessary and returns an exit code."""
        return self.code

    @with_lock
    def lookup(self, translation: Tuple[str, ...]) -> str:
        """Returns the first translation for the steno outline ``translation`` using
        all the filters.
        """
        return self._dictionaries.lookup(translation)

    @with_lock
    def raw_lookup(self, translation: Tuple[str, ...]) -> str:
        """Like :meth:`lookup`, but without any of the filters."""
        return self._dictionaries.raw_lookup(translation)

    @with_lock
    def lookup_from_all(self, translation: Tuple[str, ...]):
        """Returns all translations for the steno outline ``translation`` using
        all the filters.
        """
        return self._dictionaries.lookup_from_all(translation)

    @with_lock
    def raw_lookup_from_all(self, translation: Tuple[str, ...]):
        """Like :meth:`lookup_from_all`, but without any of the filters."""
        return self._dictionaries.raw_lookup_from_all(translation)

    @with_lock
    def reverse_lookup(self, translation: str):
        """Returns the list of steno outlines that translate to ``translation``."""
        return self._dictionaries.reverse_lookup(translation)

    @with_lock
    def casereverse_lookup(self, translation: str):
        """Like :meth:`reverse_lookup`, but performs a case-insensitive lookup."""
        return self._dictionaries.casereverse_lookup(translation)

    @with_lock
    def add_dictionary_filter(
        self, dictionary_filter: Callable[[Tuple[str, ...], str], bool]
    ) -> None:
        """Adds ``dictionary_filter`` to the list of dictionary filters.

        See :attr:`StenoDictionaryCollection.filters<plover.steno_dictionary.StenoDictionaryCollection.filters>`
        for more information.
        """
        self._dictionaries.add_filter(dictionary_filter)

    @with_lock
    def remove_dictionary_filter(
        self, dictionary_filter: Callable[[Tuple[str, ...], str], bool]
    ) -> None:
        """Removes ``dictionary_filter`` from the list of dictionary filters."""
        self._dictionaries.remove_filter(dictionary_filter)

    @with_lock
    def get_suggestions(self, translation: str):
        """Returns a list of suggestions for the specified ``translation``."""
        return Suggestions(self._dictionaries).find(translation)

    @property
    @with_lock
    def translator_state(self):
        """A :class:`_State<plover.translation._State>` object containing the
        current state of the translator.
        """
        return self._translator.get_state()

    @translator_state.setter
    @with_lock
    def translator_state(self, state):
        self._translator.set_state(state)

    @with_lock
    def clear_translator_state(self, undo: bool = False) -> None:
        """Resets the translator to an empty state, as if Plover had just started up,
        clearing the entire translation stack.

        If ``undo`` is ``True``, this also reverts all previous translations on the
        stack (which could include a lot of backspaces).
        """
        if undo:
            state = self._translator.get_state()
            if state.translations:
                self._formatter.format(state.translations, (), None)
        self._translator.clear_state()

    @property
    @with_lock
    def starting_stroke_state(self) -> StartingStrokeState:
        """A :class:`StartingStrokeState` representing the initial state of the
        formatter.
        """
        return StartingStrokeState(
            self._formatter.start_attached,
            self._formatter.start_capitalized,
            self._formatter.space_char,
        )

    @starting_stroke_state.setter
    @with_lock
    def starting_stroke_state(self, state):
        self._formatter.start_attached = state.attach
        self._formatter.start_capitalized = state.capitalize
        self._formatter.space_char = state.space_char

    @with_lock
    def add_translation(
        self,
        strokes: Tuple[str, ...],
        translation: str,
        dictionary_path: Optional[str] = None,
    ) -> None:
        """Adds a steno entry mapping the steno outline ``strokes`` to
        ``translation`` in the dictionary at ``dictionary_path``, if specified,
        or the first writable dictionary.
        """
        if dictionary_path is None:
            dictionary_path = self._dictionaries.first_writable().path
        self._dictionaries.set(strokes, translation, path=dictionary_path)
        self._dictionaries.save(path_list=(dictionary_path,))

    @property
    @with_lock
    def dictionaries(self):
        """A
        :class:`StenoDictionaryCollection<plover.steno_dictionary.StenoDictionaryCollection>`
        of all the dictionaries Plover has loaded for the current system.

        This includes disabled dictionaries and dictionaries that failed to load.
        """
        return self._dictionaries

    # Hooks.

    def _trigger_hook(self, hook, *args, **kwargs):
        for callback in self._hooks[hook]:
            try:
                callback(*args, **kwargs)
            except Exception:
                log.error("hook %r callback %r failed", hook, callback, exc_info=True)

    @with_lock
    def hook_connect(self, hook: str, callback: Callable[..., Any]) -> None:
        """Adds ``callback`` to the list of handlers that are called when the ``hook``
        hook gets triggered. Raises a ``KeyError`` if ``hook`` is not in
        :data:`HOOKS`.

        The expected signature of the callback is depends on the hook; see
        :ref:`engine-hooks` for more information.
        """
        self._hooks[hook].append(callback)

    @with_lock
    def hook_disconnect(self, hook: str, callback: Callable[..., Any]) -> None:
        """Removes ``callback`` from the list of handlers that are called when
        the ``hook`` hook is triggered. Raises a ``KeyError`` if ``hook`` is not in
        :data:`HOOKS`, and a ``ValueError`` if ``callback`` was never added as
        a handler in the first place.
        """
        self._hooks[hook].remove(callback)
