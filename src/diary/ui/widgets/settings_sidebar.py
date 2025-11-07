"""Sidebar with all the settings"""

from pathlib import Path
from typing import cast

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QCheckBox,
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from diary.config import settings
from diary.models import Notebook
from diary.ui.ui_utils import import_from_pdf, show_info_dialog, show_progress_dialog
from diary.utils.encryption import SecureEncryption


class SettingsSidebar(QDockWidget):
    """Sidebar with all the settings"""

    last_index: int = 0
    pdf_imported: pyqtSignal = pyqtSignal()
    pass_changed: pyqtSignal = pyqtSignal(object)  # tuple[new_pass_derived, salt]

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
        mouse_checkbox.setChecked(settings.MOUSE_ENABLED)
        _ = mouse_checkbox.checkStateChanged.connect(self._toggle_mouse)

        pressure_checkbox = QCheckBox()
        pressure_checkbox.setText("Pressure enabled")
        pressure_checkbox.setChecked(settings.USE_PRESSURE)
        _ = pressure_checkbox.checkStateChanged.connect(self._toggle_pressure)

        smoothing_checkbox = QCheckBox()
        smoothing_checkbox.setText("Stroke smoothing enabled")
        smoothing_checkbox.setChecked(settings.SMOOTHING_ENABLED)
        _ = smoothing_checkbox.checkStateChanged.connect(self._toggle_smoothing)

        import_btn = QPushButton()
        import_btn.setText("Import PDF")
        _ = import_btn.clicked.connect(self._import_pdf)

        change_pw_btn = QPushButton()
        change_pw_btn.setText("Change Password")
        _ = change_pw_btn.clicked.connect(self._change_password)

        path_container = QWidget()
        self.notebook_path_txt: QLineEdit = QLineEdit()
        self.notebook_path_txt.setText(settings.NOTEBOOK_FILE_PATH.as_posix())
        self.notebook_path_txt.setEnabled(False)
        save_path_btn = QPushButton()
        save_path_btn.setText("Change path")
        _ = save_path_btn.clicked.connect(self._select_notebook_path)
        path_layout = QHBoxLayout()
        path_layout.addWidget(self.notebook_path_txt)
        path_layout.addWidget(save_path_btn)
        path_container.setLayout(path_layout)

        layout.addWidget(mouse_checkbox)
        layout.addWidget(pressure_checkbox)
        layout.addWidget(smoothing_checkbox)
        layout.addWidget(import_btn)
        layout.addWidget(change_pw_btn)
        layout.addWidget(path_container)
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

    def _toggle_smoothing(self):
        settings.SMOOTHING_ENABLED = not settings.SMOOTHING_ENABLED

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

    def _change_password(self):
        new_pass, result = QInputDialog.getText(
            self.parentWidget(),
            "Change password",
            "New password: ",
            QLineEdit.EchoMode.Password,
        )
        if not result:
            return
        new_salt = SecureEncryption.generate_salt()
        new_pass_derived = SecureEncryption.derive_key(new_pass, new_salt)
        self.pass_changed.emit((new_pass_derived, new_salt))
        _ = show_info_dialog(
            self.parentWidget(),
            "Password changed",
            "The password was changed successfully!",
        )

    def _select_notebook_path(self):
        result, _ = QFileDialog.getSaveFileName(
            self.parentWidget(),
            "Notebook save destination",
            directory=settings.NOTEBOOK_FILE_PATH.as_posix(),
        )
        if not result:
            return
        result_path = Path(result)
        # TODO: Check if it's a usable location (permissions, already exists...)
        settings.NOTEBOOK_FILE_PATH = result_path
        self.notebook_path_txt.setText(result_path.as_posix())
