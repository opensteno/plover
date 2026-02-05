from plyer import notification
import logging
import os

from plover import log, __name__ as __software_name__
from plover.oslayer.config import ASSETS_DIR

APPNAME = __software_name__.capitalize()
APPICON = os.path.join(ASSETS_DIR, "plover.ico")

# Windows NOTIFYICONDATAW limits
_MAX_TITLE = 60  # leave some margin (spec is 64)
_MAX_BODY = 250  # leave some margin (spec is 256)


def _flatten(s: str) -> str:
    # Remove newlines/tabs that can expand length; collapse whitespace.
    return " ".join(s.replace("\r", " ").replace("\n", " ").replace("\t", " ").split())


def _truncate(s: str, limit: int) -> str:
    s = _flatten(s)
    if len(s) <= limit:
        return s
    # keep room for ellipsis
    if limit <= 1:
        return s[:limit]
    return s[: limit - 1] + "…"


class NotificationHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.setLevel(log.WARNING)
        self.setFormatter(
            log.NoExceptionTracebackFormatter("%(levelname)s: %(message)s")
        )

    def handle(self, record):
        level = record.levelno
        message = self.format(record)

        title = _truncate(APPNAME, _MAX_TITLE)
        body = _truncate(message, _MAX_BODY)

        # Reasonable timeouts
        if level <= log.INFO:
            timeout = 10
        elif level <= log.WARNING:
            timeout = 15
        else:
            timeout = 60

        notification.notify(
            app_name=title,
            app_icon=APPICON,
            title=title,
            message=body,
            timeout=timeout,
        )
