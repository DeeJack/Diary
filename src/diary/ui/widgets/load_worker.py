"""Load the notebook on another thread"""

import logging
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal

from diary.models import Notebook
from diary.models.dao.archive_dao import ArchiveDAO
from diary.models.dao.migration import ArchiveMigration
from diary.models.page import Page
from diary.utils.encryption import SecureBuffer, SecureEncryption


class LoadWorker(QObject):
    """Worker that loads notebooks in a separate thread"""

    # Signals
    finished: pyqtSignal = pyqtSignal(list)  # list[Notebook]
    error: pyqtSignal = pyqtSignal(str)
    progress: pyqtSignal = pyqtSignal(int, int)  # current, total

    def __init__(
        self,
        file_path: Path,
        key_buffer: SecureBuffer,
        salt: bytes | None = None,
    ):
        super().__init__()
        self.file_path: Path = file_path
        self.key_buffer: SecureBuffer = key_buffer
        self.salt: bytes | None = salt
        self._is_cancelled: bool = False
        self.logger: logging.Logger = logging.getLogger("LoadWorker")

    def run(self):
        """Main work function"""
        try:
            if self._is_cancelled:
                return

            self.logger.debug("Loading notebooks...")

            def progress_callback(current: int, total: int):
                if not self._is_cancelled:
                    self.progress.emit(current, total)

            if not self.file_path.exists():
                notebooks = [Notebook([Page()])]
            else:
                file_format = ArchiveDAO.detect_format(self.file_path)
                if file_format == "archive_v2":
                    notebooks, assets_by_notebook = ArchiveDAO.load_all(
                        self.file_path,
                        self.key_buffer,
                        progress_callback,
                    )
                else:
                    if self.salt is None:
                        self.salt = SecureEncryption.read_salt_from_file(self.file_path)
                    notebooks, assets_by_notebook = ArchiveMigration.migrate_notebooks(
                        self.file_path,
                        self.file_path,
                        self.key_buffer,
                        self.salt,
                        progress_callback,
                    )

                for notebook in notebooks:
                    assets = assets_by_notebook.get(notebook.notebook_id)
                    if assets:
                        ArchiveMigration.inject_asset_data(notebook, assets)

                if not notebooks:
                    notebooks = [Notebook([Page()])]

            if not self._is_cancelled:
                self.finished.emit(notebooks)
        except (IOError, OSError, FileNotFoundError, ValueError) as e:
            self.error.emit(str(e))

    def cancel(self):
        """Cancel the operation"""
        self._is_cancelled = True
