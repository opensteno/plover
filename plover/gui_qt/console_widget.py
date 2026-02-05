import os
import signal
import subprocess
import sys
import threading

from PySide6.QtCore import (
    Signal,
)
from PySide6.QtGui import QFontDatabase, QFontMetrics
from PySide6.QtWidgets import QWidget

from plover.gui_qt.console_widget_ui import Ui_ConsoleWidget


NULL = open(os.devnull, "r+b")


class ConsoleWidget(QWidget, Ui_ConsoleWidget):
    textOutput = Signal(str)
    processFinished = Signal(object)

    def __init__(self, popen=None):
        super().__init__()
        self.setupUi(self)
        self.textOutput.connect(self.output.append)
        self._popen = subprocess.Popen if popen is None else popen
        self._proc = None
        self._thread = None
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        metrics = QFontMetrics(font)
        self.output.setMinimumSize(80 * metrics.maxWidth(), 24 * metrics.height())
        self.output.setCurrentFont(font)

    def run(self, args):
        assert self._thread is None
        if sys.platform.startswith("win32"):
            # Make it possible to interrupt by sending a Ctrl+C event.
            kwargs = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        else:
            kwargs = {}
        self._proc = self._popen(
            args, stdin=NULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **kwargs
        )
        self._thread = threading.Thread(target=self._subprocess)
        self._thread.start()

    def terminate(self):
        assert self._proc is not None
        if sys.platform.startswith("win32"):
            sig = signal.CTRL_C_EVENT
        else:
            sig = signal.SIGINT
        self._proc.send_signal(sig)
        try:
            self._proc.wait(10)
        except subprocess.TimeoutExpired:
            self._proc.terminate()
        self._thread.join()

    def _subprocess(self):
        while True:
            try:
                line = self._proc.stdout.readline()
            except Exception:
                break
            if not line:
                break
            line = line.decode()
            if line.endswith(os.linesep):
                line = line[: -len(os.linesep)]
            print(line)
            self.textOutput.emit(line)
        self.processFinished.emit(self._proc.wait())
