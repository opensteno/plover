# Metas

To define a meta called `example_meta`, add the name as an entry point:

```ini
[options.entry_points]
plover.meta =
  example_meta = plover_my_plugin.meta:example
```

The meta can be used in dictionary entries:

```json
{
  "S-": "{:example_meta:argument}",
  "T-": "{:example_meta}"
}
```

Metas are implemented as **functions** that take a
{class}`formatting._Context<plover.formatting._Context>` and an optional string
argument. If an argument is not passed in the dictionary entry, it will be `''`.
The meta function returns a {class}`formatting._Action<plover.formatting._Action>`
which will then be applied to the existing output.

You will want to use either
{meth}`context.new_action()<plover.formatting._Context.new_action>` or
{meth}`context.copy_last_action()<plover.formatting._Context.copy_last_action>`
as the basis for the output value. Previously translated text can also be accessed.

```python
# plover_my_plugin/meta.py


def example(ctx, argument):
    pass
```

% TODO:
% - new actions (plover-current-time?)
% - accessing/modifying previous actions (retro_currency)
% - document context/actions API
