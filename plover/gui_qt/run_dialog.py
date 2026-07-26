from PySide6.QtWidgets import QDialog, QDialogButtonBox

from plover.gui_qt.console_widget import ConsoleWidget
from plover.gui_qt.run_dialog_ui import Ui_RunDialog


class RunDialog(QDialog, Ui_RunDialog):
    def __init__(self, run_args, popen=None):
        super().__init__()
        self.setupUi(self)
        self._console = ConsoleWidget(popen)
        self.layout().replaceWidget(self.console, self._console)
        self.buttonBox.button(QDialogButtonBox.StandardButton.Close).setHidden(True)
        self._console.processFinished.connect(self.on_process_finished)
        self._console.run(run_args)
        self._successful = None

    def on_process_finished(self, returncode):
        self._successful = returncode == 0
        self.buttonBox.button(QDialogButtonBox.StandardButton.Cancel).setHidden(True)
        self.buttonBox.button(QDialogButtonBox.StandardButton.Close).setHidden(False)

    def reject(self):
        if self._successful is not None:
            super().done(
                getattr(
                    QDialog.DialogCode, "Accepted" if self._successful else "Rejected"
                )
            )
            return
        self._console.terminate()


if __name__ == "__main__":
    import sys

    from PySide6.QtWidgets import QApplication

    app = QApplication([])
    dlg = RunDialog(sys.argv[1:])
    dlg.show()
    app.exec()
