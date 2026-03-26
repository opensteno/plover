# `plover.gui_qt` -- Qt plugins

```{py:module} plover.gui_qt

```

This module provides the Qt-based steno engine, which is necessary for
developing GUI tool plugins.

````{class} Engine
This is largely just a subclass of
{class}`StenoEngine<plover.engine.StenoEngine>`,
except for some Qt-specific logic, such as the signals below.

Since Qt's signals will fit better into the Qt processing model than
Plover's default [engine hooks](engine-hooks), GUI plugins should
use the API provided by this engine over the built-in one where possible.

```{method} signal_connect(name: str, callback: Function)
Registers `callback` as a callback to be called when the `name`
hook is triggered. The callback is called with the arguments shown
in {ref}`engine-hooks` when the hook is triggered.

The individual Qt signals are also available below for convenience, for
example if you need to trigger them manually. For example,
`engine.signal_lookup.emit()` would trigger the `lookup` hook.
The arguments for each signal are shown in {ref}`engine-hooks`.
```

```{attribute} signal_stroked
:type: QSignal

The signal version of the `stroked` hook.
```

```{attribute} signal_translated
:type: QSignal

The signal version of the `translated` hook.
```

```{attribute} signal_machine_state_changed
:type: QSignal

The signal version of the `machine_state_changed` hook.
```

```{attribute} signal_output_changed
:type: QSignal

The signal version of the `output_changed` hook.
```

```{attribute} signal_config_changed
:type: QSignal

The signal version of the `config_changed` hook.
```

```{attribute} signal_dictionaries_loaded
:type: QSignal

The signal version of the `dictionaries_loaded` hook.
```

```{attribute} signal_send_string
:type: QSignal

The signal version of the `send_string` hook.
```

```{attribute} signal_send_backspaces
:type: QSignal

The signal version of the `send_backspaces` hook.
```

```{attribute} signal_send_key_combination
:type: QSignal

The signal version of the `send_key_combination` hook.
```

```{attribute} signal_add_translation
:type: QSignal

The signal version of the `add_translation` hook.
```

```{attribute} signal_focus
:type: QSignal

The signal version of the `focus` hook.
```

```{attribute} signal_configure
:type: QSignal

The signal version of the `configure` hook.
```

```{attribute} signal_lookup
:type: QSignal

The signal version of the `lookup` hook.
```

```{attribute} signal_suggestions
:type: QSignal

The signal version of the `suggestions` hook.
```

```{attribute} signal_quit
:type: QSignal

The signal version of the `quit` hook.
```
````

(qt-tools)=

## Tools

```{py:module} plover.gui_qt.tool

```

Plover provides a helper class for creating GUI tools:

````{class} Tool(engine)
A subclass of `QDialog` for creating GUI tools. When writing a GUI tool,
you would typically subclass both {class}`Tool` *and* some generated code
class (named `Ui_YourTool` or something) to take care of the UI setup.

```{method} setupUi(widget)
Sets up the user interface for this tool. You would typically call this
in the `__init__` method of your subclass to actually build the UI.
Make sure to pass `self` in if you do.
```

```{attribute} TITLE
:type: str

The title that would show up in the main window's toolbar and the
tools list in the main menu.
```

```{attribute}  __doc__
:type: str

The text description that shows up in the tooltip on hover. If 
not set, this would fallback to the TITLE
```

```{attribute} ICON
:type: str

The path to the icon for this tool, usually of the form `:/icon.svg`.
This file should be included as a resource in the GUI plugin.
```

```{attribute} ROLE
:type: str

A unique name to identify this tool when saving and loading state.
```

```{attribute} SHORTCUT
:type: str

A keyboard shortcut to activate this window, for example `Ctrl+F`.
If shortcut is in use by Plover, this will override it.

```

```{method} _save_state(settings: QSettings)

Saves the current state of this tool to `settings`.
Call ``settings.setValue(key, value)`` to store individual properties
in this settings object.
```

```{method} _restore_state(settings: QSettings)

Restores the current state of this tool from `settings`.
Call `settings.value(key)` to retrieve values for the desired
properties.
```
````

(qt-machine-options)=

## Machine Options

```{py:module} plover.gui_qt.machine_options

```

````{class} MachineOption
Represents the user interface for manipulating machine-specific
configuration options. Each {class}`MachineOption` class is also a subclass
of a `QWidget` and is set up with a UI, similar to
{class}`Tool<plover.gui_qt.tool.Tool>` above.

This isn't itself a real class, though; in order to support a machine
options UI for your machine, subclass `QWidget` and your UI class of
choice and implement the method and attribute below.

```{method} setValue(value)
Sets the contained value to `value`.
```

```{attribute} valueChanged
:type: QSignal

A signal that gets emitted when the contained value is changed.
Callbacks are called with the new value.
```
````

```{class} KeyboardOption
A :class:`MachineOption` class for keyboard-specific options.
```

```{class} SerialOption
A :class:`MachineOption` class for serial connection-specific options.
```

## Utilities

```{py:module} plover.gui_qt.utils

```

```{function} ToolBar(*action_list: List[QAction]) -> QToolBar
Returns a toolbar with a button for each of the specified actions.
```

```{function} find_menu_actions(menu: QMenu) -> Dict[str, QAction]
Returns a dictionary mapping action names to action objects in `menu`.
This traverses the entire menu tree recursively.
```
