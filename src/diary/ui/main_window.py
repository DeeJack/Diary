"""The main window of the Diary application, containing all other Widgets"""

import logging
import secrets
import sys
from typing import override

from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import (
    QInputDialog,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QStatusBar,
)
from PyQt6.QtCore import Qt

from diary.models import NotebookDAO
from diary.ui.widgets.notebook_widget import NotebookWidget
from diary.config import settings
from diary.utils.encryption import SecureBuffer, SecureEncryption


class MainWindow(QMainWindow):
    """Main window of the application, containing all other Widgets"""

    logger: logging.Logger = logging.Logger("Main Window")

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Diary Application")
        self.setGeometry(100, 100, 800, 600)
        self.setStyleSheet("background-color: #2C2C2C;")

        self.show()

        self.logger.debug("Opening input dialog")
        password, ok = QInputDialog.getText(
            self,
            "Password Required",
            "Enter your encryption password:",
            QLineEdit.EchoMode.Password,
        )

        self.logger.debug("Input dialog result: %s", ok)

        if ok and password:
            try:
                if settings.NOTEBOOK_FILE_PATH.exists():
                    self.logger.debug("Previous notebook exists, reading salt")

                    # Read salt from existing file
                    salt = SecureEncryption.read_salt_from_file(
                        settings.NOTEBOOK_FILE_PATH
                    )
                else:
                    self.logger.debug(
                        "Previous notebook does not exists, creating new salt"
                    )

                    # Generate new salt for new file
                    salt = secrets.token_bytes(SecureEncryption.SALT_SIZE)

                self.logger.debug("Deriving new key from password and salt")
                key_buffer = SecureEncryption.derive_key(password, salt)

                # Clear password from memory immediately
                password_bytes = bytearray(password.encode("utf-8"))
                for i, _ in enumerate(password_bytes):
                    password_bytes[i] = 0
                password = ""

                status_bar = self.statusBar()
                if status_bar:
                    status_bar.showMessage("Password accepted. Key derived.", 5000)
                self.open_notebook(key_buffer, salt)
            except ValueError as e:
                _ = QMessageBox.critical(self, "Error", str(e))
                _ = self.close()
                sys.exit(0)
        else:
            _ = self.close()
            sys.exit(0)

    def open_notebook(self, key_buffer: SecureBuffer, salt: bytes):
        """Opens the Notebook with the given password"""
        old_notebook = NotebookDAO.load(settings.NOTEBOOK_FILE_PATH, key_buffer)
        self.logger.debug("Loaded notebook, creating and opening NotebookWidget")
        self.notebook: NotebookWidget = NotebookWidget(  # pyright: ignore[reportUninitializedInstanceVariable]
            key_buffer, salt, self.statusBar() or QStatusBar(), old_notebook
        )
        self.notebook.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCentralWidget(self.notebook)

    @override
    def closeEvent(self, a0: QCloseEvent | None):
        self.logger.debug("Close app event!")
        if a0 and hasattr(self, "notebook") and self.notebook:
            self.notebook.save()
            a0.accept()
