# Copyright (c) 2013 Hesky Fisher
# See LICENSE.txt for details.

"""A module to handle logging."""

import os
import sys
import logging
import traceback

from logging.handlers import RotatingFileHandler
from logging import INFO, WARNING

from plover.oslayer.config import CONFIG_DIR


LOG_FORMAT = "%(asctime)s [%(threadName)s] %(levelname)s: %(message)s"
LOG_FILENAME = os.path.realpath(os.path.join(CONFIG_DIR, "plover.log"))
LOG_MAX_BYTES = 10000000
LOG_COUNT = 9

STROKE_LOG_FORMAT = "%(asctime)s %(message)s"


class NoExceptionTracebackFormatter(logging.Formatter):
    """Custom formatter for formatting exceptions without traceback."""

    def format(self, record):
        # Calls to formatException are cached.
        # (see http://bugs.python.org/issue1295)
        orig_exc_text = record.exc_text
        record.exc_text = None
        try:
            return super().format(record)
        finally:
            record.exc_text = orig_exc_text

    def formatException(self, exc_info):
        etype, evalue, tb = exc_info
        lines = traceback.format_exception_only(etype, evalue)
        return "".join(lines)


class FileHandler(RotatingFileHandler):
    def __init__(self, filename=LOG_FILENAME, format=LOG_FORMAT):
        super().__init__(
            filename, maxBytes=LOG_MAX_BYTES, backupCount=LOG_COUNT, encoding="utf-8"
        )
        self.setFormatter(logging.Formatter(format))


class PrintHandler(logging.StreamHandler):
    """Handler using L{print_} to output messages."""

    def __init__(self, format=LOG_FORMAT):
        super().__init__(sys.stderr)
        self.setFormatter(logging.Formatter(format))


class Logger:
    def __init__(self):
        self._print_handler = PrintHandler()
        self._print_handler.setLevel(WARNING)
        self._file_handler = None
        self._platform_handler = None
        self._logger = logging.getLogger("plover")
        self._logger.addHandler(self._print_handler)
        self._logger.setLevel(INFO)
        self._stroke_filename = None
        self._stroke_logger = logging.getLogger("plover-strokes")
        self._stroke_logger.setLevel(INFO)
        self._stroke_handler = None
        self._log_strokes = False
        self._log_translations = False

    def has_platform_handler(self):
        return self._platform_handler is not None

    def setup_platform_handler(self):
        if self.has_platform_handler():
            return
        NotificationHandler = None
        try:
            from plover.oslayer.log import NotificationHandler
        except Exception:
            self.info("could not import platform gui log", exc_info=True)
            return
        try:
            handler = NotificationHandler()
            self.addHandler(handler)
        except Exception:
            self.info("could not initialize platform gui log", exc_info=True)
            return
        self._platform_handler = handler

    def set_level(self, level):
        self._print_handler.setLevel(level)
        if self._file_handler is not None:
            self._file_handler.setLevel(level)
        self.setLevel(level)

    def setup_logfile(self):
        assert self._file_handler is None
        self._file_handler = FileHandler()
        self._file_handler.setLevel(self.level)
        self._logger.addHandler(self._file_handler)

    def _setup_stroke_logging(self):
        is_logging = self._stroke_handler is not None
        must_log = (
            self._log_strokes or self._log_translations
        ) and self._stroke_filename is not None
        if must_log:
            if is_logging:
                start_logging = stop_logging = (
                    self._stroke_filename != self._stroke_handler.baseFilename
                )
            else:
                stop_logging = False
                start_logging = True
        else:
            stop_logging = is_logging
            start_logging = False
        if stop_logging:
            self._stroke_logger.removeHandler(self._stroke_handler)
            self._stroke_handler.close()
            self._stroke_handler = None
        if start_logging:
            self._stroke_handler = FileHandler(
                filename=self._stroke_filename, format=STROKE_LOG_FORMAT
            )
            self._stroke_logger.addHandler(self._stroke_handler)

    def set_stroke_filename(self, filename=None):
        if filename is not None:
            filename = os.path.realpath(filename)
        if self._stroke_filename == filename:
            return
        assert filename != LOG_FILENAME
        self.info("set_stroke_filename(%s)", filename)
        self._stroke_filename = filename
        self._setup_stroke_logging()

    def enable_stroke_logging(self, enable):
        if self._log_strokes == enable:
            return
        self.info("enable_stroke_logging(%s)", enable)
        self._log_strokes = enable
        self._setup_stroke_logging()

    def enable_translation_logging(self, enable):
        if self._log_translations == enable:
            return
        self.info("enable_translation_logging(%s)", enable)
        self._log_translations = enable
        self._setup_stroke_logging()

    def log_stroke(self, stroke):
        if not self._log_strokes or self._stroke_handler is None:
            return
        self._stroke_logger.info("%s", stroke)

    def log_translation(self, undo, do, prev):
        if not self._log_translations or self._stroke_handler is None:
            return
        # TODO: Figure out what to actually log here.
        for u in undo:
            self._stroke_logger.info("*%s", u)
        for d in do:
            self._stroke_logger.info(d)

    # Delegate calls to _logger.
    def __getattr__(self, name):
        return getattr(self._logger, name)


# Set up default logger.
__logger = Logger()

# The following functions direct all input to __logger.
debug = __logger.debug
info = __logger.info
warning = __logger.warning
error = __logger.error
set_level = __logger.set_level
add_handler = __logger.addHandler
remove_handler = __logger.removeHandler
has_platform_handler = __logger.has_platform_handler
setup_platform_handler = __logger.setup_platform_handler
# Strokes/translation logging.
set_stroke_filename = __logger.set_stroke_filename
stroke = __logger.log_stroke
translation = __logger.log_translation
enable_stroke_logging = __logger.enable_stroke_logging
enable_translation_logging = __logger.enable_translation_logging
# Logfile support.
setup_logfile = __logger.setup_logfile
