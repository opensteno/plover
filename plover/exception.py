# Copyright (c) 2011 Joshua Harlan Lifton.
# See LICENSE.txt for details.

"""Custom exceptions used by Plover.

The exceptions in this module are typically caught in the main GUI
loop and displayed to the user as an alert dialog.

"""


class InvalidConfigurationError(Exception):
    "Raised when there is something wrong in the configuration."
