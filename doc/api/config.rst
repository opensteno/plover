``plover.config`` -- Configuration
==================================

.. automodule:: plover.config
   :no-members:

.. autoclass:: plover.config.Config
   :members:
   :member-order: bysource
   :special-members: __getitem__, __setitem__

.. autoexception:: plover.config.InvalidConfigOption

.. autoclass:: plover.config.DictionaryConfig
   :members:
   :member-order: bysource

.. _config-keys:

Configuration Options
---------------------

Below is the list of all available configuration keys:

Output
~~~~~~

.. describe:: space_placement

   When writing translations, whether to add spaces before or after each
   translation. Possible values are ``Before Output`` and ``After Output``.
   By default, will add spaces *before* translations.

.. describe:: start_attached

   Whether to delete the space before the translation when the initial
   stroke is translated. ``False`` by default.

.. describe:: start_capitalized

   Whether to capitalize the translation when the initial stroke is
   translated. ``False`` by default.

.. describe:: undo_levels

   The maximum number of translations Plover is allowed to undo. 100 by default.

   Each stroke that performs a translation is added onto an undo stack, and
   undo strokes (such as ``*``) remove translations from this stack.
   ``undo_levels`` defines the maximum number of translations in the stack.

Logging
~~~~~~~

.. describe:: log_file_name

   The path to the stroke log file, either absolute or expressed relative to
   :data:`CONFIG_DIR<plover.oslayer.config.CONFIG_DIR>`. ``strokes.log`` by default.

   This only sets the path for stroke logs; main Plover logs are always
   written to ``plover.log``.

.. describe:: enable_stroke_logging

   Whether to log strokes. ``False`` by default.

.. describe:: enable_translation_logging

   Whether to log translations. ``False`` by default.

Interface
~~~~~~~~~

.. describe:: start_minimized

   Whether to hide the main window when Plover starts up. ``False`` by default.

.. describe:: show_stroke_display

   Whether to show the paper tape when Plover starts up. ``False`` by default.

.. describe:: show_suggestions_display

   Whether to show the suggestions window when Plover starts up. ``False`` by default.

.. describe:: translation_frame_opacity

   The opacity of the Add Translation tool, in percent. 100 by default.

.. describe:: classic_dictionaries_display_order

   The order the dictionaries are displayed in the main window.
   ``True`` displays the highest priority dictionary at the bottom;
   ``False`` displays it at the top. ``False`` by default.

Plugins
~~~~~~~

.. describe:: enabled_extensions

   The list of extensions that are enabled.

Machine
~~~~~~~

.. describe:: auto_start

   Whether to enable Plover output when it starts up. ``False`` by default.

.. describe:: machine_type

   The name of the currently active machine. ``Keyboard`` by default.

.. describe:: machine_specific_options

   A dictionary of configuration options specific to the current machine.
   Consult your machine plugin's documentation to see the available properties.
   For the default machine plugins, the following options are available:

   .. describe:: arpeggiate

      Whether to enable arpeggiate mode on the keyboard. ``False`` by default.

   .. describe:: port

      The serial port for serial connections. No default value.

      The value will most likely be different between platforms; Windows uses COM
      ports, e.g. ``COM3``, whereas Unix-like platforms use device paths, e.g.
      ``/dev/cu.usbmodem14403`` or ``/dev/ttyACM0``.

   .. describe:: baudrate

      The baud rate for serial connections. 9600 by default.

   .. describe:: bytesize

      The number of bits in a byte for serial connections. 8 by default.

   .. describe:: parity

      The parity bit mode for serial connections, one of
      ``N`` (none), ``O`` (odd), ``E`` (even), ``M`` (mark) or ``S`` (space).
      ``N`` by default.

   .. describe:: stopbits

      The number of stop bits for serial connections. 1 by default.

   .. describe:: timeout

      The read timeout for serial connections in seconds. 2.0 (2 seconds) by default.

   .. describe:: xonxoff

      Whether to use XON/XOFF flow control for serial connections.
      ``False`` by default.

   .. describe:: rtscts

      Whether to use RTS/CTS flow control for serial connections.
      ``False`` by default.

System
~~~~~~

.. describe:: system_name

   The name of the current steno system. This is the same system that
   :mod:`plover.system` refers to. ``English Stenotype`` by default.

.. describe:: system_keymap

   A :class:`Keymap<plover.machine.keymap.Keymap>` mapping between machine
   keys and steno keys in the current steno system.

   If the system defines a keymap in :data:`KEYMAPS<plover.system.KEYMAPS>`
   for the current machine type, that will be the default value; otherwise,
   the machine may define a
   :attr:`KEYMAP_MACHINE_TYPE<plover.machine.base.StenotypeBase.KEYMAP_MACHINE_TYPE>`
   that describes a similar machine to fall back on. If that is not available
   either, the default value is an empty keymap.

.. describe:: dictionaries

   A list of :class:`DictionaryConfig` representing the list of dictionaries
   Plover uses to translate strokes for the current steno system. The
   dictionaries should be listed in order of decreasing priority.
