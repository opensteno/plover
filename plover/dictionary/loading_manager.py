# Copyright (c) 2013 Hesky Fisher
# See LICENSE.txt for details.

"""Centralized place for dictionary loading operation."""

import threading
import time

from plover.dictionary.base import load_dictionary
from plover.resource import resource_timestamp
from plover import log


class DictionaryLoadingManager:
    def __init__(self, state_change_callback):
        """
        Parameters:
        state_change_callback -- A function that will be called when any dictionary is loaded
            with two parameters: the filename and the loaded StenoDictionary object
            (or an instance of ErroredDictionary if the load fails).
        """
        self._state_change_callback = state_change_callback
        self.dictionaries = {}

    def __len__(self):
        return len(self.dictionaries)

    def __getitem__(self, filename):
        return self.dictionaries[filename].get()

    def __contains__(self, filename):
        return filename in self.dictionaries

    def start_loading(self, filename):
        op = self.dictionaries.get(filename)
        if op is not None and not op.needs_reloading():
            return op
        log.info(
            "%s dictionary: %s", "loading" if op is None else "reloading", filename
        )
        op = DictionaryLoadingOperation(filename, self._state_change_callback)
        self.dictionaries[filename] = op
        return op

    def unload_outdated(self):
        for filename, op in list(self.dictionaries.items()):
            if op.needs_reloading():
                del self.dictionaries[filename]

    def load(self, filenames):
        start_time = time.time()
        self.dictionaries = {f: self.start_loading(f) for f in filenames}
        results = [self.dictionaries[f].get() for f in filenames]
        log.info(
            "loaded %u dictionaries in %.3fs", len(results), time.time() - start_time
        )
        return results


class DictionaryLoadingOperation:
    def __init__(self, filename, state_change_callback):
        """
        Parameters:
        filename -- Path to dictionary file.
        state_change_callback -- A function that will be called when the load is finished
            with two parameters: the filename and the loaded StenoDictionary object
            (or an instance of ErroredDictionary if the load fails).
        """
        self._state_change_callback = state_change_callback
        self.loading_thread = threading.Thread(target=self.load)
        self.filename = filename
        self.result = None
        self.loading_thread.start()

    def needs_reloading(self):
        try:
            new_timestamp = resource_timestamp(self.filename)
        except Exception:
            # Bad resource name, permission denied, path
            # does not exist, ...
            new_timestamp = None
        # If no change in timestamp: don't reload.
        if new_timestamp == self.result.timestamp:
            return False
        # If we could not get the new timestamp:
        # the dictionary is not available anymore,
        # attempt to reload to notify the user.
        if new_timestamp is None:
            return True
        # If we're here, and no previous timestamp exists,
        # then the file was previously inaccessible, reload.
        if self.result.timestamp is None:
            return True
        # Otherwise, just compare timestamps.
        return self.result.timestamp < new_timestamp

    def load(self):
        timestamp = None
        try:
            timestamp = resource_timestamp(self.filename)
            self.result = load_dictionary(self.filename)
        except Exception as e:
            log.debug("loading dictionary %s failed", self.filename, exc_info=True)
            from plover.engine import ErroredDictionary

            self.result = ErroredDictionary(self.filename, e)
            self.result.timestamp = timestamp
        self._state_change_callback(self.filename, self.result)

    def get(self):
        self.loading_thread.join()
        return self.result
