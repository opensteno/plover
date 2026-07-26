# Machines

To define a new machine called `Example Machine`, add the name as an entry
point to your `setup.py`:

```ini
[options.entry_points]
plover.machine =
  Example Machine = plover_my_plugin.machine:ExampleMachine
```

Machines are implemented as **classes** that inherit from one of a few machine
classes. The example shown uses the
{class}`ThreadedStenotypeBase<plover.machine.base.ThreadedStenotypeBase>` class
as it is the most common use case, but you can build machine plugins off of the
{class}`StenotypeBase<plover.machine.base.StenotypeBase>`,
{class}`SerialStenotypeBase<plover.machine.base.SerialStenotypeBase>`, or other
classes depending on your needs.

```python
# plover_my_plugin/machine.py

from plover.machine.base import ThreadedStenotypeBase


class ExampleMachine(ThreadedStenotypeBase):
    KEYS_LAYOUT: str = "0 1 2 3 4 5 6 7 8 9 10"

    def __init__(self, params):
        super().__init__()
        self._params = params

    def run(self):
        self._ready()
        while not self.finished.wait(1):
            self._notify(self.keymap.keys_to_actions(["1"]))

    def start_capture(self):
        super().start_capture()

    def stop_capture(self):
        super().stop_capture()

    @classmethod
    def get_option_info(cls):
        pass
```

The `_notify` method should be called whenever a stroke is received. It takes
a set of key names in the current system (it's possible to convert from machine
key names to system key names (or "actions") with {meth}`Keymap.keys_to_actions<plover.machine.keymap.Keymap.keys_to_actions>`) and then tells the steno engine the key input that just occurred.

There are 3 ways to configure the keymap:

- Add an entry for the machine in a system plugin's default bindings
  definition ({data}`KEYMAPS<plover.system.KEYMAPS>`)
- The user can manually set the keymap in the Machine section in the
  configuration, along with any other additional configuration if a
  machine_option plugin is available for the machine type
- Define a class variable {data}`KEYMAP_MACHINE_TYPE<plover.machine.base.StenotypeBase.KEYMAP_MACHINE_TYPE>`, which means that the
  default configuration is the same as the default configuration of the
  specified machine.

See {doc}`../api/machine` for more information.

## Machine Options

If your machine requires additional configuration options, add a machine
options entry point:

```ini
[options.entry_points]
plover.gui_qt.machine_options =
  plover_my_plugin.machine:ExampleMachine = plover_my_plugin.machine:ExampleMachineOption
```

Machine options plugins are implemented as Qt widget **classes**:

```python
# plover_my_plugin/machine.py

from PyQt5.QtWidgets import QWidget


class ExampleMachineOption(QWidget):
    def setValue(self, value):
        pass
```

The process for developing these is similar to that for [GUI tools](gui_tools).
See {ref}`qt-machine-options` for more information.

% TODO:
% - serial machine API
% - implementing protocols
% - Qt UI for machine options
