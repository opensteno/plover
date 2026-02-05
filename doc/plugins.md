# Plugins

As of version 4.0, Plover's functionality can be supplemented by plugins,
from the tools available in the GUI to the types of dictionaries supported.
Much of Plover's built-in functionality is implemented using the same plugin
system.

See below for more information on how to install and use plugins, and the
{doc}`plugin_dev` for more technical information on how to develop and publish
plugins.

## Installing Plugins

There are two ways to install plugins:

- **Plugins Manager**: Use Plover's built-in Plugins Manager to browse
  available Plover plugins by name, selected the desired plugin and click
  Install. Installed plugins will be available the next time you restart
  Plover.

- **Command line**: If the Plugins Manager is not working, or the plugin you
  are trying to install has not been published, you can use the command-line
  [plugin installer](plugin-installer).

## Types of Plugins

- **Dictionaries**: Support other dictionary formats besides Plover's native
  JSON format. They can either be other text formats or completely code-driven
  dictionaries. To use a dictionary plugin, just add a dictionary of the
  desired format to your list of dictionaries.

  Plover is bundled with the JSON and RTF/CRE dictionary plugins by default.

- **Machines**: Support new input protocols, such as the serial input from
  various professional stenography machines or even MIDI keyboards. To use a
  machine plugin, set the Machine in your configuration to the desired
  protocol, and modify the options (if available) according to your specific
  machine's configuration.

  Plover comes with the following machine plugins installed:

  - Gemini PR
  - Keyboard
  - Passport
  - Plover HID
  - ProCAT
  - Stentura
  - TX Bolt

- **Systems**: Define new key layouts and theories. This lets Plover support
  stenographic layouts other than the standard American Stenotype system,
  such as Michela ([`plover-michela`](https://pypi.org/project/plover-michela/))
  or Korean CAS ([`plover-korean`](https://github.com/nsmarkop/plover_korean)).

  To use a system plugin, set the System in your configuration to the desired
  system. If a key layout is available for your currently selected machine,
  you should be able to use the system automatically; otherwise, you will
  need to set key mappings in the Machine section of your configuration.
  Plover comes with the standard English Stenotype layout by default.

- **Commands**: Allow Plover to run arbitrary commands in response to a
  stroke. The logic can interact with the stenography engine itself but can
  also do completely separate tasks. For example,
  [`plover-vlc-commands`](https://pypi.org/project/plover-vlc-commands/) can
  be used to control the VLC media player with Plover strokes.

  To use a command plugin after it's been installed, add an entry to your
  dictionary that translates to `{PLOVER:<command_name>}` or
  `{PLOVER:<command_name>:<argument>}`.

- **Macros and Metas**: Add or modify translations in the translator,
  typically for transforming previously entered text. Macros have access to
  the entire translation and can perform transformations on the raw stroke
  input, whereas metas only have access to the translated output.

  To use a meta plugin, add an entry to your dictionary that translates to
  `{:<meta_name>}` or `{:<meta_name>:<argument>}`; for a macro, add an
  entry that translates to `=<macro_name>` or `=<macro_name>:<argument>`.

  Much of Plover's built-in functionality, such as undoing strokes or
  formatting currency amounts, is implemented using macros and metas.

- **GUI Plugins**: User-facing GUI tools, like the built-in Suggestions and
  Lookup tools. GUI plugins are automatically loaded at startup, and can be
  accessed by clicking on its icon on the toolbar.

  Plover comes with the following GUI tools:

  - Add Translation
  - Lookup
  - Paper Tape
  - Suggestions

- **Extensions**: Can be used to execute arbitrary code. They are started when
  Plover starts and can be enabled or disabled in the Plugins section of the
  configuration. They are ideal for background processes that should run
  concurrently to the main stenography engine but can be used to perform
  one-time actions as well.

  For example, the
  [`plover-websocket-server`](https://github.com/nsmarkop/plover_websocket_server)
  extension plugin runs a
  WebSocket server in the background that publishes a stream of Plover events.
