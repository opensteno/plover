# Extensions

Extension plugins are implemented as **classes**. The initializer should take
only a {class}`StenoEngine<plover.engine.StenoEngine>` as a parameter.

```ini
[options.entry_points]
plover.extension =
  example_extension = plover_my_plugin.extension:Extension
```

```python
# plover_my_plugin/extension.py


class Extension:
    def __init__(self, engine):
        # Called once to initialize an instance which lives until Plover exits.
        self.engine = engine

    def start(self):
        # Called to start the extension or when the user enables the extension.
        # It can be used to start a new thread for example.
        pass

    def stop(self):
        # Called when Plover exits or the user disables the extension.
        pass
```

Extensions can interact with the engine through the
{class}`StenoEngine<plover.engine.StenoEngine>` API, and receive engine
events through its {ref}`engine hooks<engine-hooks>` mechanism.

For example, a simple extension plugin that just writes strokes to a file,
using the {js:func}`stroked<stroked>` hook:

```python
class StrokeLogger:
    def __init__(self, engine):
        self.engine = engine
        self.output_file = None

    def start(self):
        self.output_file = open("strokes.txt")

        # self.on_stroked gets called on every stroke
        self.engine.hook_connect("stroked", self.on_stroked)

    def stop(self):
        self.engine.hook_connect("stroked", self.on_stroked)
        self.output_file.close()

    def on_stroked(self, stroke):
        print(stroke, file=self.output_file)
```
