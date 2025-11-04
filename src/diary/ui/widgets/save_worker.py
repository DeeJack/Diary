"""Save the notebook on another thread"""

import logging
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QStatusBar

from diary.models import Notebook, NotebookDAO
from diary.utils.backup import BackupManager
from diary.utils.encryption import SecureBuffer


class SaveWorker(QObject):
    """Worker that runs in a separate thread"""

    # Signals
    finished: pyqtSignal = pyqtSignal(bool, str)  # (success, message)
    error: pyqtSignal = pyqtSignal(str)

    def __init__(
        self,
        notebook: Notebook,
        file_path: Path,
        key_buffer: SecureBuffer,
        salt: bytes,
        status_bar: QStatusBar,
    ):
        super().__init__()
        self.notebook: Notebook = notebook
        self.file_path: Path = file_path
        self.key_buffer: SecureBuffer = key_buffer
        self.salt: bytes = salt
        self._is_cancelled: bool = False
        self.logger: logging.Logger = logging.getLogger("SaveWorker")
        self.backup_manager: BackupManager = BackupManager()
        self.status_bar: QStatusBar = status_bar

    def run(self):
        """Main work function"""
        try:
            if self._is_cancelled:
                return

            self.status_bar.showMessage("Saving...")
            self.logger.debug("Saving notebook (%d pages)...", len(self.notebook.pages))
            NotebookDAO.saves(
                [self.notebook], self.file_path, self.key_buffer, self.salt
            )
            self.status_bar.showMessage("Save completed!")

            self.logger.debug("Creating backup...")
            self.status_bar.showMessage("Creating backup...")
            self.backup_manager.save_backups()
            self.status_bar.showMessage("Backup completed!")

            if not self._is_cancelled:
                self.finished.emit(True, "Saved successfully")
        except (IOError, OSError, FileNotFoundError) as e:
            self.error.emit(str(e))
            self.finished.emit(False, f"Save failed: {e}")

    def cancel(self):
        """Cancel the operation"""
        self._is_cancelled = True
