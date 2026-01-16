"""Save the notebook on another thread"""

import logging
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal

from diary.models import Notebook
from diary.models.dao.archive_dao import ArchiveDAO
from diary.models.dao.migration import ArchiveMigration
from diary.utils.backup import BackupManager
from diary.utils.encryption import SecureBuffer


class SaveWorker(QObject):
    """Worker that runs in a separate thread"""

    # Signals
    finished: pyqtSignal = pyqtSignal(bool, str)  # (success, message)
    error: pyqtSignal = pyqtSignal(str)

    def __init__(
        self,
        all_notebooks: list[Notebook],
        file_path: Path,
        key_buffer: SecureBuffer,
        salt: bytes,
    ):
        super().__init__()
        self.all_notebooks: list[Notebook] = all_notebooks
        self.file_path: Path = file_path
        self.key_buffer: SecureBuffer = key_buffer
        self.salt: bytes = salt
        self._is_cancelled: bool = False
        self.logger: logging.Logger = logging.getLogger("SaveWorker")
        self.backup_manager: BackupManager = BackupManager()

    def run(self):
        """Main work function"""
        try:
            if self._is_cancelled:
                return

            self.logger.debug("Saving notebooks in archive format...")

            if self.all_notebooks:
                assets_by_notebook = {
                    notebook.notebook_id: ArchiveMigration.extract_assets_from_notebook(
                        notebook
                    )
                    for notebook in self.all_notebooks
                }

                ArchiveDAO.save_all(
                    self.all_notebooks,
                    assets_by_notebook,
                    self.file_path,
                    self.key_buffer,
                    self.salt,
                )

            self.logger.debug("Creating backup...")
            self.backup_manager.save_backups()

            if not self._is_cancelled:
                self.finished.emit(True, "Saved successfully")
        except (IOError, OSError, FileNotFoundError) as e:
            self.error.emit(str(e))
            self.finished.emit(False, f"Save failed: {e}")

    def cancel(self):
        """Cancel the operation"""
        self._is_cancelled = True
