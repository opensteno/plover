``plover.engine`` -- Steno engine
====================================================================

.. automodule:: plover.engine
   :no-members:

.. autoclass:: plover.engine.StenoEngine

   .. automethod:: plover.engine.StenoEngine._in_engine_thread

   .. automethod:: plover.engine.StenoEngine.start

   .. automethod:: plover.engine.StenoEngine.quit

   .. automethod:: plover.engine.StenoEngine.restart

   .. automethod:: plover.engine.StenoEngine.run

   .. automethod:: plover.engine.StenoEngine.join

   .. automethod:: plover.engine.StenoEngine.load_config

   .. automethod:: plover.engine.StenoEngine.reset_machine

   .. automethod:: plover.engine.StenoEngine._send_engine_command

   .. automethod:: plover.engine.StenoEngine.toggle_output

   .. automethod:: plover.engine.StenoEngine.set_output

   .. automethod:: plover.engine.StenoEngine.__getitem__

   .. automethod:: plover.engine.StenoEngine.__setitem__

   .. automethod:: plover.engine.StenoEngine.get_suggestions

   .. automethod:: plover.engine.StenoEngine.clear_translator_state

   .. automethod:: plover.engine.StenoEngine.hook_connect

   .. automethod:: plover.engine.StenoEngine.hook_disconnect

   The following methods simply provide a way to access the underlying
   :class:`StenoDictionaryCollection<plover.steno_dictionary.StenoDictionaryCollection>`.
   See the documentation there for more complete information.

   .. automethod:: plover.engine.StenoEngine.lookup

   .. automethod:: plover.engine.StenoEngine.raw_lookup

   .. automethod:: plover.engine.StenoEngine.lookup_from_all

   .. automethod:: plover.engine.StenoEngine.raw_lookup_from_all

   .. automethod:: plover.engine.StenoEngine.reverse_lookup

   .. automethod:: plover.engine.StenoEngine.casereverse_lookup

   .. automethod:: plover.engine.StenoEngine.add_dictionary_filter

   .. automethod:: plover.engine.StenoEngine.remove_dictionary_filter

   .. automethod:: plover.engine.StenoEngine.add_translation

.. autoclass:: plover.engine.StartingStrokeState

.. autoclass:: plover.engine.MachineParams

.. autoclass:: plover.engine.ErroredDictionary

.. _engine-hooks:

Engine Hooks
------------

Plover uses engine hooks to allow plugins to listen to engine events. By
calling :meth:`engine.hook_connect<plover.engine.StenoEngine.hook_connect>` and passing the
name of one of the hooks below and a function, you can write handlers that are
called when Plover hooks get triggered.

.. plover:hook:: stroked(stroke: plover.steno.Stroke)

   The user just sent a stroke.

.. plover:hook:: translated(old, new)

.. plover:hook:: machine_state_changed(machine_type: str, machine_state: str)

   Either the machine type was changed by the user, or the connection state
   of the machine changed. ``machine_type`` is the name of the machine
   (e.g. ``Gemini PR``), and ``machine_state`` is one of ``stopped``,
   ``initializing``, ``connected`` or ``disconnected``.

.. plover:hook:: output_changed(enabled: bool)

   The user requested to either enable or disable steno output. ``enabled`` is
   ``True`` if output is enabled, ``False`` otherwise.

.. plover:hook:: config_changed(config: Dict[str, Any])

   The configuration was changed, or it was loaded for the first time.
   ``config`` is a dictionary containing *only* the changed fields. Call the
   hook function with the :attr:`StenoEngine.config<plover.engine.StenoEngine.config>`
   to initialize your plugin based on the full configuration.

.. plover:hook:: dictionaries_loaded(dictionaries: plover.steno_dictionary.StenoDictionaryCollection)

   The dictionaries were loaded, either when Plover starts up or the system
   is changed or when the engine is reset.

.. plover:hook:: send_string(s: str)

   Plover just sent the string ``s`` over keyboard output.

.. plover:hook:: send_backspaces(b: int)

   Plover just sent backspaces over keyboard output. ``b`` is the number of
   backspaces sent.

.. plover:hook:: send_key_combination(c: str)

   Plover just sent a keyboard combination over keyboard output. ``c`` is a
   string representing the keyboard combination, for example ``Alt_L(Tab)``.

.. plover:hook:: add_translation()

   The Add Translation command was activated -- open the Add Translation tool.

.. plover:hook:: focus()

   The Show command was activated -- reopen Plover's main window and bring it
   to the front.

.. plover:hook:: configure()

   The Configure command was activated -- open the configuration window.

.. plover:hook:: lookup()

   The Lookup command was activated -- open the Lookup tool.

.. plover:hook:: suggestions()

   The Suggestions command was activated -- open the Suggestions tool.

.. plover:hook:: quit()

   The Quit command was activated -- wrap up any pending tasks and quit Plover.
