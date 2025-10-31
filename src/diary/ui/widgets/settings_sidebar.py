"""Sidebar with all the settings"""

from typing import cast

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QCheckBox,
    QDockWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from diary.config import settings
from diary.models import Notebook
from diary.ui.utils import import_from_pdf, show_progress_dialog


class SettingsSidebar(QDockWidget):
    """Sidebar with all the settings"""

    last_index: int = 0
    pdf_imported: pyqtSignal = pyqtSignal()

    def __init__(self, parent: QWidget | None, notebook: Notebook):
        super().__init__("Settings", parent)
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self._notebook: Notebook = notebook

        main_container = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        mouse_checkbox = QCheckBox()
        mouse_checkbox.setText("Mouse enabled")
        _ = mouse_checkbox.checkStateChanged.connect(self._toggle_mouse)

        pressure_checkbox = QCheckBox()
        pressure_checkbox.setText("Pressure enabled")
        _ = pressure_checkbox.checkStateChanged.connect(self._toggle_pressure)

        import_btn = QPushButton()
        import_btn.setText("Import PDF")
        _ = import_btn.clicked.connect(self._import_pdf)

        change_pw_btn = QPushButton()
        change_pw_btn.setText("Change Password")

        layout.addWidget(mouse_checkbox)
        layout.addWidget(pressure_checkbox)
        layout.addWidget(import_btn)
        layout.addWidget(change_pw_btn)
        layout.setSpacing(20)
        layout.addStretch()
        main_container.setLayout(layout)
        main_container.setContentsMargins(10, 10, 10, 10)
        self.setWidget(main_container)

        self.setFixedWidth(300)

    def _toggle_mouse(self):
        settings.MOUSE_ENABLED = not settings.MOUSE_ENABLED

    def _toggle_touch(self):
        settings.TOUCH_ENABLED = not settings.TOUCH_ENABLED

    def _toggle_pressure(self):
        settings.USE_PRESSURE = not settings.USE_PRESSURE

    def create_toggle_action(self):
        """Create action to open/close the sidebar"""
        sidebar_action = cast(QAction, self.toggleViewAction())
        sidebar_action.setText("Toggle Settings")
        sidebar_action.setShortcut("Ctrl+,")
        return sidebar_action

    def _import_pdf(self):
        dialog = show_progress_dialog(
            self.parentWidget(), "Importing...", "Importing PDF file"
        )
        pages = import_from_pdf()
        if pages:
            self._notebook.pages.extend(pages)
            self.pdf_imported.emit()
            _ = dialog.close()
