"""Save Manager to handle all saving functionality for the notebook"""

import logging
from pathlib import Path

from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import QStatusBar

from diary.config import settings
from diary.models import Notebook, NotebookDAO
from diary.ui.widgets.save_worker import SaveWorker
from diary.utils.backup import BackupManager
from diary.utils.encryption import SecureBuffer


class SaveManager(QObject):
    """Manages all saving operations for the notebook"""

    # Signals
    save_completed: pyqtSignal = pyqtSignal(bool, str)  # (success, message)
    save_error: pyqtSignal = pyqtSignal(str)  # error message

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
        self.status_bar: QStatusBar = status_bar

        self.logger: logging.Logger = logging.getLogger("SaveManager")
        self.backup_manager: BackupManager = BackupManager()

        # Save state
        self.is_notebook_dirty: bool = False
        self.is_saving: bool = False

        # Threading
        self.save_thread: QThread | None = None
        self.save_worker: SaveWorker | None = None

        # Auto-save timer
        self.auto_save_timer: QTimer = QTimer()
        self.auto_save_timer.setInterval(1000 * settings.AUTOSAVE_NOTEBOOK_TIMEOUT)
        _ = self.auto_save_timer.timeout.connect(self.save_async)
        self.auto_save_timer.start()

    def mark_dirty(self) -> None:
        """Mark the notebook as having unsaved changes"""
        self.is_notebook_dirty = True

    def is_dirty(self) -> bool:
        """Check if the notebook has unsaved changes"""
        return self.is_notebook_dirty

    def save(self) -> None:
        """Save notebook synchronously"""
        if not self.is_notebook_dirty:
            self.logger.debug("Skipping save due to no changes")
            return

        self.logger.debug("Saving notebook (%d pages)...", len(self.notebook.pages))
        self.status_bar.showMessage("Saving...")

        try:
            NotebookDAO.saves(
                [self.notebook],
                self.file_path,
                self.key_buffer,
                self.salt,
            )
            self.status_bar.showMessage("Save completed!")
            self.is_notebook_dirty = False

            # Create backup after successful save
            self._create_backup()

            self.save_completed.emit(True, "Saved successfully")
        except (IOError, OSError, FileNotFoundError) as e:
            self.logger.error("Error saving notebook: %s", e)
            self.status_bar.showMessage("Save failed!")
            self.save_error.emit(str(e))

    def save_async(self) -> None:
        """Save notebook in separate thread"""
        if self.is_saving or not self.is_notebook_dirty:
            return

        self.is_saving = True
        self._setup_save_worker()
        self.logger.debug("Starting async save")
        if self.save_thread:
            self.save_thread.start()

    def _setup_save_worker(self) -> None:
        """Setup the save worker and thread"""
        self.save_thread = QThread()
        self.save_worker = SaveWorker(
            self.notebook,
            self.file_path,
            self.key_buffer,
            self.salt,
            self.status_bar,
        )
        self.save_worker.moveToThread(self.save_thread)

        # Connect signals
        _ = self.save_thread.started.connect(self.save_worker.run)
        _ = self.save_worker.finished.connect(self._on_save_finished)
        _ = self.save_worker.error.connect(self._on_save_error)

        # Cleanup connections
        _ = self.save_worker.finished.connect(self.save_thread.quit)
        _ = self.save_thread.finished.connect(self.save_worker.deleteLater)
        _ = self.save_thread.finished.connect(self.save_thread.deleteLater)

    def _on_save_finished(self, success: bool, message: str) -> None:
        """Handle save completion"""
        self.is_saving = False
        if success:
            self.is_notebook_dirty = False

        self.logger.debug("Save finished with result %s, message %s", success, message)
        self.save_completed.emit(success, message)

    def _on_save_error(self, error_msg: str) -> None:
        """Handle save error"""
        self.logger.error("Error while saving: %s", error_msg)
        self.is_saving = False
        self.save_error.emit(error_msg)

    def _create_backup(self) -> None:
        """Create backup after successful save"""
        try:
            self.logger.debug("Creating backup...")
            self.status_bar.showMessage("Creating backup...")
            self.backup_manager.save_backups()
            self.status_bar.showMessage("Backup completed!")
        except (FileNotFoundError, IOError, OSError) as e:
            self.logger.error("Error creating backup: %s", e)

    def force_save_on_close(self) -> None:
        """Force synchronous save when closing application"""
        if self.is_notebook_dirty:
            self.save()

    def stop_auto_save(self) -> None:
        """Stop the auto-save timer"""
        self.auto_save_timer.stop()

    def start_auto_save(self) -> None:
        """Start the auto-save timer"""
        self.auto_save_timer.start()
