import signal
import sys
from pathlib import Path

from PySide6.QtCore import (
    QCoreApplication,
    QLibraryInfo,
    QTimer,
    QtMsgType,
    QTranslator,
    qInstallMessageHandler,
)
from PySide6.QtWidgets import QApplication, QMessageBox

from plover import _, __version__, log
from plover import __name__ as __software_name__
from plover.gui_qt.engine import Engine
from plover.oslayer.config import CONFIG_DIR
from plover.oslayer.keyboardcontrol import KeyboardEmulation

# Disable input hook to avoid getting spammed when using the debugger.
# import pdb
# pdb.set_trace()


class Application:
    def __init__(self, config, controller, use_qt_notifications):
        # This is done dynamically so localization
        # support can be configure beforehand.
        from plover.gui_qt.main_window import MainWindow

        self._app = None
        self._win = None
        self._engine = None
        self._translator = None

        QCoreApplication.setApplicationName(__software_name__.capitalize())
        QCoreApplication.setApplicationVersion(__version__)
        QCoreApplication.setOrganizationName("Open Steno Project")
        QCoreApplication.setOrganizationDomain("openstenoproject.org")

        self._app = QApplication([sys.argv[0], "-name", "plover"])

        # Apply custom stylesheet if present.
        stylesheet_path = Path(CONFIG_DIR) / "plover.qss"
        if stylesheet_path.exists():
            log.info("using stylesheet at: %s", stylesheet_path)
            self._app.setStyleSheet(stylesheet_path.read_text())

        # Enable localization of standard Qt controls.
        log.info("setting language to: %s", _.lang)
        self._translator = QTranslator()
        translations_dir = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
        self._translator.load("qtbase_" + _.lang, translations_dir)
        self._app.installTranslator(self._translator)

        QApplication.setQuitOnLastWindowClosed(False)

        self._app.engine = self._engine = Engine(
            config, controller, KeyboardEmulation()
        )
        # On macOS, quitting through the dock will result
        # in a direct call to `QCoreApplication.quit`.
        self._app.aboutToQuit.connect(self._app.engine.quit)

        signal.signal(signal.SIGINT, lambda signum, stack: self._engine.quit())

        # Make sure the Python interpreter runs at least every second,
        # so signals have a chance to be processed.
        self._timer = QTimer()
        self._timer.timeout.connect(lambda: None)
        self._timer.start(1000)

        self._win = MainWindow(self._engine, use_qt_notifications)

    def __del__(self):
        del self._win
        del self._app
        del self._engine
        del self._translator

    def run(self):
        self._app.exec()
        return self._engine.join()


def show_error(title, message):
    print(f"{title}: {message}")
    if QApplication.instance() is None:
        QApplication([])
    QMessageBox.critical(None, title, message)


def default_excepthook(*exc_info):
    log.error("Qt GUI error", exc_info=exc_info)


def default_message_handler(msg_type, msg_log_context, msg_string):
    log_fn = {
        QtMsgType.QtDebugMsg: log.debug,
        QtMsgType.QtInfoMsg: log.info,
        QtMsgType.QtWarningMsg: log.warning,
    }.get(msg_type, log.error)
    details = []
    if msg_log_context.file is not None:
        details.append(f"{msg_log_context.file}:{msg_log_context.line}")
    if msg_log_context.function is not None:
        details.append(msg_log_context.function)
    if details:
        details = " [{}]".format(", ".join(details))
    else:
        details = ""
    log_fn("Qt: %s%s", msg_string, details)


def main(config, controller):
    # Setup internationalization support.
    use_qt_notifications = not log.has_platform_handler()
    # Log GUI exceptions that make it back to the event loop.
    if sys.excepthook is sys.__excepthook__:
        sys.excepthook = default_excepthook
    # Capture and log Qt messages.
    qInstallMessageHandler(default_message_handler)
    app = Application(config, controller, use_qt_notifications)
    code = app.run()
    del app
    return code
