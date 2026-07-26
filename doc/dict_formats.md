# Dictionary Formats

Plover supports multiple proprietary steno dictionary formats, as well as
some open formats widely used by the Open Steno community. At a high level,
there are two main types of dictionaries: static and programmatic.

## Static Dictionaries

Static dictionaries consist of entries mapping steno outlines to translations.
This is the simplest type of dictionary, and most Plover dictionaries will
be of this form.

### JSON

The most common format for steno dictionaries in Plover is the **JavaScript
Object Notation** (JSON) format. This consists of a series of key-value pairs
separated by commas and surrounded by curly brackets `{}`:

```json
{
  "KAT": "cat",
  "KAT/HROG": "catalog",
  "KA/TA/HROG": "catalog",
  "-S": "{^s}"
}
```

In each key-value pair, the key is the [canonical steno notation](steno_notation)
of the outline, with the strokes separated by slashes, and the value is the
translation for that outline in Plover's [translation language](translation_language).
This format is used for dictionaries because it matches Plover's internal
storage format almost exactly.

### RTF/CRE

Another common dictionary format, which is also supported by most proprietary
steno software, is the
[**Rich Text Format** with Court Reporting Extensions](http://www.legalxml.org/workgroups/substantive/transcripts/cre-spec.htm)
(RTF/CRE) format. It was designed as an interchange format between steno
systems, so Plover supports some of the features implemented into the format.

```rtf
{\rtf1\ansi\cxrev100\cxdict
{\*\cxs KAT}cat
{\*\cxs KAT/HROG}catalog
{\*\cxs KA/TA/HROG}catalog
{\*\cxs -S}\cxds s{\*\cxcomment -s suffix}
}
```

In RTF dictionaries, while the steno outline is also written in the same
notation, the translation isn't written in Plover's translation language;
instead it uses RTF-specific formatting controls that translate to different
commands for each steno system that supports it. RTF also supports some
entry-level metadata, such as comments and historical usage data, but these
can't be read by Plover.

It's generally not recommended to maintain RTF dictionaries, since they can be
slow to parse and the format isn't especially well defined, but this is often
an option if, for example, professional stenographers would also like to use
their personal dictionaries with Plover.

### Proprietary Formats

Plover also supports some proprietary software's native dictionary formats,
with the help of some plugins:

- [plover-casecat-dictionary](https://github.com/marnanel/plover_casecat_dictionary) -- Stenograph Case CATalyst dictionaries (`.sgdct`)
- [plover-digitalcat-dictionary](https://github.com/marnanel/plover_digitalcat_dictionary) -- Stenovations digitalCAT dictionaries (`.dct`)
- [plover-eclipse-dictionary](https://github.com/marnanel/plover_eclipse_dictionary) -- Advantage Software Eclipse dictionaries (`.dix`)

## Programmatic Dictionaries

Programmatic dictionaries, instead of containing a list of entries, calculate
translations on the fly, the moment Plover requests them. This is most useful
for heavily regular dictionaries like a symbol system or a syllabic theory.

The [plover-python-dictionary](https://github.com/benoit-pierre/plover_python_dictionary)
plugin adds support for programmatic dictionaries written in Python, which can
be used in Plover just like static ones.

Programmatic dictionaries primarily expose a lookup function, which calculates
a translation for a given steno outline. Some dictionaries may also provide a
reverse-lookup function, which calculates all the possible outlines that
translate to a particular text.

```{data} LONGEST_KEY
The maximum number of strokes that this dictionary can translate. Plover uses
this value to optimize dictionary lookups by only using this dictionary when
looking up outlines this length or shorter.

This attribute is **required**.
```

```{function} lookup(outline: Tuple[str]) -> str
:noindex:

Given an outline which is a tuple of steno strokes, returns the translation for
this outline, or raises a `KeyError` when no translation is available. The
translation should be in Plover's [translation language](translation_language).

This function is **required**.
```

```{function} reverse_lookup(translation: str) -> List[Tuple[str]]
:noindex:

Given a translation in Plover's [translation language](translation_language),
returns the list of possible outlines that translate to it. The list may be
empty if there are no possible outlines in this dictionary.

This function is *optional*; the dictionary still works without implementing
it, but it will not support searching in the Lookup tool.
```

Here is an example of a very basic programmatic dictionary which just
translates `KP-PL` to `example`:

```python
LONGEST_KEY = 1


def lookup(outline):
    assert len(outline) == 1

    stroke = outline[0]
    if stroke == "KP-PL":
        return "example"
    else:
        raise KeyError


def reverse_lookup(translation):
    if translation == "example":
        return [("KP-PL",)]
    else:
        return []
```
