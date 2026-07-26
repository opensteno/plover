# Dictionaries

To define a dictionary format with the file extension `.abc`, add this name
(without the `.`) as an entry point:

```ini
[options.entry_points]
plover.dictionary =
  abc = plover_my_plugin.dictionary:ExampleDictionary
```

Dictionary plugins are implemented as **classes** inheriting from
{class}`StenoDictionary<plover.steno_dictionary.StenoDictionary>`. Override the
`_load` and `_save` methods *at least* to provide functionality to read and
write your desired dictionary format.

```python
# plover_my_plugin/dictionary.py

from plover.steno_dictionary import StenoDictionary


class ExampleDictionary(StenoDictionary):
    readonly = False

    def _load(self, filename):
        # If you are not maintaining your own state format, self.update is usually
        # called here to add strokes / definitions to the dictionary state.
        pass

    def _save(self, filename):
        pass
```

Note that setting `readonly` to `True` on your dictionary class will make
it so the user is not able to modify a dictionary of that type in the UI.

For example, a simplified version of the JSON dictionary implementation:

```python
class JsonDictionary(StenoDictionary):
    def _load(self, filename):
        with open(filename) as fp:
            d = dict(json.load(fp))

            # Inserts the entries into the dictionary
            self.update((normalize_steno(k), v) for k, v in d.items())

    def _save(self, filename):
        with open(filename, "w") as fp:
            entries = [("/".join(k), v) for k, v in self.items()]
            json.dump(entries, fp)
```

Some dictionary formats, such as Python dictionaries, may require implementing
other parts of the class as well. See the documentation for
{class}`StenoDictionary<plover.steno_dictionary.StenoDictionary>` for more
information.
