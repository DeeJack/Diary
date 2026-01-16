"""Load the notebook on another thread"""

import logging
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal

from diary.models import Notebook, NotebookDAO
from diary.utils.encryption import SecureBuffer


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

            notebooks = NotebookDAO.loads(
                self.file_path,
                self.key_buffer,
                progress_callback,
                salt=self.salt,
            )

            if not self._is_cancelled:
                self.finished.emit(notebooks)
        except (IOError, OSError, FileNotFoundError, ValueError) as e:
            self.error.emit(str(e))

    def cancel(self):
        """Cancel the operation"""
        self._is_cancelled = True
