# Copyright (c) 2013 Hesky Fisher
# See LICENSE.txt for details.

# TODO: maybe move this code into the StenoDictionary itself. The current saver
# structure is odd and awkward.
# TODO: write tests for this file

"""Common elements to all dictionary formats."""

import functools
import threading
from os.path import splitext

from plover.registry import registry


def _get_dictionary_class(filename):
    extension = splitext(filename)[1].lower()[1:]
    try:
        dict_module = registry.get_plugin("dictionary", extension).obj
    except KeyError:
        raise ValueError(
            "Unsupported extension: {}. Supported extensions: {}".format(
                extension,
                ", ".join(
                    plugin.name for plugin in registry.list_plugins("dictionary")
                ),
            )
        )
    return dict_module


def _locked(fn):
    lock = threading.Lock()

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with lock:
            fn(*args, **kwargs)

    return wrapper


def _threaded(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        t = threading.Thread(target=fn, args=args, kwargs=kwargs)
        t.start()

    return wrapper


def create_dictionary(resource, threaded_save=True):
    """Create a new dictionary.

    The format is inferred from the extension.

    Note: the file is not created! The resulting dictionary save
    method must be called to finalize the creation on disk.
    """
    d = _get_dictionary_class(resource).create(resource)
    if threaded_save:
        d.save = _threaded(_locked(d.save))
    return d


def load_dictionary(resource, threaded_save=True):
    """Load a dictionary from a file.

    The format is inferred from the extension.
    """
    d = _get_dictionary_class(resource).load(resource)
    if not d.readonly and threaded_save:
        d.save = _threaded(_locked(d.save))
    return d
