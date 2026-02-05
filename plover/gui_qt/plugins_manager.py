from threading import Thread
import atexit
import html
import os
import sys

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QDialog,
    QMessageBox,
    QTableWidgetItem,
    QInputDialog,
)

from plover import log
from plover.gui_qt.tool import Tool
from plover.gui_qt.info_browser import InfoBrowser
from plover.gui_qt.plugins_manager_ui import Ui_PluginsManager
from plover.gui_qt.run_dialog import RunDialog
from plover.plugins_manager.registry import Registry
from plover.plugins_manager.utils import description_to_html
from plover.plugins_manager.__main__ import pip


class PluginsManager(Tool, Ui_PluginsManager):
    TITLE = "Plugins Manager"
    ROLE = "plugins_manager"
    ICON = ":/resources/plugins_manager.svg"

    # We use a class instance so the state is persistent
    # accross different executions of the dialog when
    # the user does not restart.
    _packages = None
    _packages_updated = Signal()

    def __init__(self, engine):
        super().__init__(engine)
        self.setupUi(self)
        self.uninstall_button.setEnabled(False)
        self.install_button.setEnabled(False)
        self._engine = engine
        self.info = InfoBrowser()
        self.info_frame.layout().addWidget(self.info)
        self.table.sortByColumn(1, Qt.SortOrder.AscendingOrder)
        self._packages_updated.connect(self._on_packages_updated)
        if self._packages is None:
            PluginsManager._packages = Registry()
        self._on_packages_updated()
        self.refresh()

    def _need_restart(self):
        for state in self._packages:
            if state.status in ("removed", "updated"):
                return True
        return False

    def _on_packages_updated(self):
        self.restart_button.setEnabled(self._need_restart())
        self.progress.hide()
        self.refresh_button.show()
        self._update_table()
        self.setEnabled(True)

    def _update_table(self):
        self.table.setCurrentItem(None)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self._packages))
        for row, state in enumerate(self._packages):
            for column, attr in enumerate("status name version summary".split()):
                item = QTableWidgetItem(getattr(state, attr, "N/A"))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, column, item)
        self.table.resizeColumnsToContents()
        self.table.setSortingEnabled(True)

    def _get_state(self, row):
        name = self.table.item(row, 1).data(Qt.ItemDataRole.DisplayRole)
        return self._packages[name]

    def _get_selection(self):
        can_install = []
        can_uninstall = []
        for item in self.table.selectedItems():
            if item.column() != 0:
                continue
            state = self._get_state(item.row())
            if state.status in ("installed", "updated"):
                can_uninstall.append(state.name)
            elif state.status in ("outdated",):
                can_uninstall.append(state.name)
                can_install.append(state.name)
            elif state.status != "unsupported" and state.latest:
                can_install.append(state.name)
        return can_install, can_uninstall

    @staticmethod
    def _run(args):
        dialog = RunDialog(args, popen=pip)
        code = dialog.exec()
        # dialog.destroy()
        return code

    @Slot()
    def handle_selection_change(self):
        can_install, can_uninstall = self._get_selection()
        self.uninstall_button.setEnabled(bool(can_uninstall))
        self.install_button.setEnabled(bool(can_install))
        self._clear_info()
        current_item = self.table.currentItem()
        if current_item is None:
            return
        metadata = self._get_state(current_item.row()).metadata
        if metadata is None or metadata.name is None:
            return
        prologue = "<h1>%s (%s)</h1>" % (
            html.escape(metadata.name),
            html.escape(metadata.version),
        )
        if metadata.author and metadata.author_email:
            prologue += '<p><b>Author: </b><a href="mailto:%s">%s</a></p>' % (
                html.escape(metadata.author_email),
                html.escape(metadata.author),
            )
        if metadata.home_page:
            prologue += '<p><b>Home page: </b><a href="%s">%s</a></p>' % (
                metadata.home_page,
                html.escape(metadata.home_page),
            )
        prologue += "<hr>"
        if metadata.description:
            description = metadata.description
            description_content_type = metadata.description_content_type
        else:
            description = metadata.summary
            description_content_type = None
        css, description = description_to_html(description, description_content_type)
        self.info.setHtml(css + prologue + description)

    @Slot()
    def restart(self):
        if self._engine is not None:
            self._engine.restart()
        else:
            atexit._run_exitfuncs()
            args = [sys.executable, "-m", __spec__.name]
            os.execv(args[0], args)

    def _update_packages(self):
        try:
            self._packages.update()
            self._packages_updated.emit()
        except BaseException:
            # gui_qt/main.py sets sys.excepthook, but this function is run in a thread
            # so it doesn't apply. We catch exceptions manually.
            log.error("Error in updating packages", exc_info=sys.exc_info())

    def _clear_info(self):
        self.info.setHtml("")

    @Slot()
    def refresh(self):
        Thread(target=self._update_packages).start()
        self._clear_info()
        self.setEnabled(False)
        self.refresh_button.hide()
        self.progress.show()

    @Slot()
    def install_from_git(self):
        url, ok = QInputDialog.getText(
            self,
            "Install from Git repo",
            "<b>WARNING: Installing plugins is a security risk.<br>"
            "A plugin from a Git repo can contain malicious code.<br>"
            "Only install it if you got it from a trusted source.</b><br><br>"
            "Enter repository link for plugin<br>"
            "(will look similar to "
            "https://github.com/user/repository.git): <br>",
        )
        if not ok or not url:
            return

        code = self._run(["install"] + ["git+" + url])
        if code == QDialog.DialogCode.Accepted:
            self._update_table()
            self.restart_button.setEnabled(True)

    @Slot()
    def install_selected_package(self):
        packages = self._get_selection()[0]
        if (
            QMessageBox.warning(
                self,
                "Install " + ", ".join(packages),
                "Installing plugins is a <b>security risk</b>. "
                "A plugin can contain virus/malware. "
                "Only install it if you got it from a trusted source."
                " Are you sure you want to proceed?",
                buttons=QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                defaultButton=QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        code = self._run(
            ["install"] + [self._packages[name].latest.requirement for name in packages]
        )
        if code == QDialog.DialogCode.Accepted:
            for name in packages:
                state = self._packages[name]
                state.current = state.latest
            self._update_table()
            self.restart_button.setEnabled(True)

    @Slot()
    def uninstall_selected_package(self):
        packages = self._get_selection()[1]
        code = self._run(["uninstall", "-y"] + packages)
        if code == QDialog.DialogCode.Accepted:
            for name in packages:
                state = self._packages[name]
                state.current = None
            self._update_table()
            self.restart_button.setEnabled(True)


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication

    app = QApplication([])
    dlg = PluginsManager(None)
    dlg.show()
    app.exec()
