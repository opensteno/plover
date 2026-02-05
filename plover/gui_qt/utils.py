from PySide6.QtCore import QSettings
from PySide6.QtGui import (
    QAction,
    QGuiApplication,
    QKeySequence,
)
from PySide6.QtWidgets import (
    QMainWindow,
    QToolBar,
    QToolButton,
    QWidget,
    QApplication,
)

from plover import _


def is_wayland():
    return "wayland" in QApplication.platformName().lower()


def ActionCopyViewSelectionToClipboard(view):
    def copy_selection_to_clipboard():
        indexes = view.selectedIndexes()
        data = view.model().mimeData(indexes)
        QGuiApplication.clipboard().setMimeData(data)

    action = QAction(_("Copy selection to clipboard"))
    action.setShortcut(QKeySequence(QKeySequence.StandardKey.Copy))
    action.triggered.connect(copy_selection_to_clipboard)
    return action


def ToolButton(action):
    button = QToolButton()
    button.setDefaultAction(action)
    return button


def ToolBar(*action_list):
    toolbar = QToolBar()
    for action in action_list:
        if action is None:
            toolbar.addSeparator()
        else:
            toolbar.addWidget(ToolButton(action))
    return toolbar


class WindowStateMixin:
    """
    Mixin class for saving and restoring window state using QSettings.

    This class is used as a mixin alongside a class that inherits from QWidget.
    It does NOT inherit from QWidget to avoid multiple inheritance issues.

    Usage:
        class MyDialog(QDialog, WindowStateMixin):
            ...
    """

    ROLE = None

    def _save_state(self, settings):
        """
        To be overwritten by subclasses to save additional state.
        """
        pass

    def save_state(self):
        assert self.ROLE
        assert isinstance(self, QWidget), (
            "WindowStateMixin must be used with a QWidget subclass"
        )

        settings = QSettings()
        settings.beginGroup(self.ROLE)
        settings.setValue("geometry", self.saveGeometry())
        if isinstance(self, QMainWindow):
            settings.setValue("state", self.saveState())
        self._save_state(settings)
        settings.endGroup()

    def _restore_state(self, settings):
        """
        To be overwritten by subclasses to restore additional state.
        """
        pass

    def restore_state(self):
        assert self.ROLE
        assert isinstance(self, QWidget), (
            "WindowStateMixin must be used with a QWidget subclass"
        )

        settings = QSettings()
        settings.beginGroup(self.ROLE)
        geometry = settings.value("geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
        if isinstance(self, QMainWindow):
            state = settings.value("state")
            if state is not None:
                self.restoreState(state)
        self._restore_state(settings)
        settings.endGroup()


def find_menu_actions(menu):
    """Recursively find and return a menu actions."""
    actions_dict = {}
    for action in menu.actions():
        name = action.objectName()
        if not name:
            sub_menu = action.menu()
            if sub_menu is None:
                continue
            actions_dict.update(find_menu_actions(sub_menu))
            name = sub_menu.objectName()
        assert name
        assert name not in actions_dict
        actions_dict[name] = action
    return actions_dict
