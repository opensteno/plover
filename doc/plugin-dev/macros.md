# Macros

To define a macro called `example_macro`, add the name as an entry point:

```ini
[options.entry_points]
plover.macro =
  example_macro = plover_my_plugin.macro:example
```

The macro can be used in dictionary entries:

```json
{
  "S-": "=example_macro:argument",
  "T-": "=example_macro"
}
```

Macros are implemented as **functions** that take a
{class}`Translator<plover.translation.Translator>` object, a
{class}`Stroke<plover.steno.Stroke>` object, and an optional string argument.
If an argument is not passed in the dictionary entry, it will be `''`.

```python
# plover_my_plugin/macro.py


def example(translator, stroke, argument):
    pass
```

Various methods of the translator can be used to either access or undo
previously translated entries, as well as apply new translations. See the
documentation for {class}`Translator<plover.translation.Translator>`
for more information.

% TODO:
% - document translator API
% - add examples
