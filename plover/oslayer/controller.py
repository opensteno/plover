from multiprocessing import connection
from threading import Thread
import errno
import os
import tempfile

from plover import log
from plover.oslayer.config import PLATFORM


class Controller:
    def __init__(self, instance="plover", authkey=b"plover"):
        if PLATFORM == "win":
            self._address = r"\\.\pipe" + "\\" + instance
            self._family = "AF_PIPE"
        else:
            self._address = os.path.join(tempfile.gettempdir(), instance + "_socket")
            self._family = "AF_UNIX"
        self._authkey = authkey
        self._listen = None
        self._thread = None
        self._message_cb = None

    @property
    def is_owner(self):
        return self._listen is not None

    def force_cleanup(self):
        assert not self.is_owner
        if PLATFORM != "win" and os.path.exists(self._address):
            os.unlink(self._address)
            return True
        return False

    def __enter__(self):
        assert self._listen is None
        try:
            self._listen = connection.Listener(
                self._address, self._family, authkey=self._authkey
            )
        except Exception as e:
            if PLATFORM == "win":
                if not isinstance(e, PermissionError):
                    raise
            else:
                if not isinstance(e, OSError) or e.errno != errno.EADDRINUSE:
                    raise
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.is_owner:
            self._listen.close()

    def _accept(self):
        conn = self._listen.accept()
        try:
            msg = conn.recv()
            if msg is None:
                return True
            self._message_cb(msg)
        finally:
            conn.close()
        return False

    def _run(self):
        while True:
            try:
                if self._accept():
                    break
            except Exception:
                log.error("handling client failed", exc_info=True)

    def _send_message(self, msg):
        conn = connection.Client(self._address, self._family, authkey=self._authkey)
        try:
            conn.send(msg)
        finally:
            conn.close()

    def send_command(self, command):
        self._send_message(("command", command))

    def start(self, message_cb):
        assert self.is_owner
        if self._thread is not None:
            return
        self._message_cb = message_cb
        self._thread = Thread(target=self._run)
        self._thread.start()

    def stop(self):
        assert self.is_owner
        if self._thread is None:
            return
        self._send_message(None)
        self._thread.join()
        self._thread = None
