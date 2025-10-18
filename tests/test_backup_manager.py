"""
Tests for the backup management system
"""

import tempfile
import json
from datetime import datetime, timedelta
from pathlib import Path
import shutil
import time
from typing import Any
from unittest.mock import patch

from diary.utils.backup import BackupManager
from diary.config import Settings


class TestBackupManager:
    """Test suite for BackupManager class"""

    def setup_method(self):
        """Set up test environment for each test"""
        # Create a temporary directory for all test files
        self.temp_dir: Path = Path(tempfile.mkdtemp())  # pyright: ignore[reportUninitializedInstanceVariable]

        # Create test settings with temp paths
        self.test_settings: Settings = Settings()  # pyright: ignore[reportUninitializedInstanceVariable]
        self.test_settings.DATA_DIR_PATH = self.temp_dir / "data"
        self.test_settings.NOTEBOOK_FILE_PATH = (
            self.test_settings.DATA_DIR_PATH / "notebook.json"
        )
        self.test_settings.BACKUP_DIR_PATH = self.temp_dir / "backup"
        self.test_settings.DAILY_BACKUP_PATH = (
            self.test_settings.BACKUP_DIR_PATH / "daily"
        )
        self.test_settings.WEEKLY_BACKUP_PATH = (
            self.test_settings.BACKUP_DIR_PATH / "weekly"
        )
        self.test_settings.MONTLY_BACKUP_PATH = (
            self.test_settings.BACKUP_DIR_PATH / "monthly"
        )
        self.test_settings.CURRENT_BACKUP_PATH = (
            self.test_settings.BACKUP_DIR_PATH / "current.enc"
        )

        # Create test notebook file
        self.test_settings.DATA_DIR_PATH.mkdir(parents=True, exist_ok=True)
        test_notebook_data: dict[str, Any] = {  # pyright: ignore[reportExplicitAny]
            "pages": [{"strokes": [], "metadata": {}}],
            "metadata": {"title": "Test Notebook"},
        }
        with open(self.test_settings.NOTEBOOK_FILE_PATH, "w") as f:
            json.dump(test_notebook_data, f)

    def teardown_method(self):
        """Clean up after each test"""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_backup_manager_initialization(self):
        """Test that BackupManager initializes correctly and creates directories"""
        with patch("diary.utils.backup.settings", self.test_settings):
            _ = BackupManager()
            assert self.test_settings.BACKUP_DIR_PATH.exists()
            assert self.test_settings.DAILY_BACKUP_PATH.exists()
            assert self.test_settings.WEEKLY_BACKUP_PATH.exists()
            assert self.test_settings.MONTLY_BACKUP_PATH.exists()

    def test_save_backups_creates_current_backup(self):
        """Test that save_backups creates a current backup file"""
        with patch("diary.utils.backup.settings", self.test_settings):
            manager = BackupManager()
            manager.save_backups()

            # Check that current backup was created
            assert self.test_settings.CURRENT_BACKUP_PATH.exists()
            assert self.test_settings.CURRENT_BACKUP_PATH.is_file()

            # Verify it's a copy of the notebook file
            with open(self.test_settings.NOTEBOOK_FILE_PATH, "r") as original:
                with open(self.test_settings.CURRENT_BACKUP_PATH, "r") as backup:
                    assert original.read() == backup.read()

    def test_maybe_promote_to_daily_creates_new_backup(self):
        """Test that daily backup is created when none exists"""
        with patch("diary.utils.backup.settings", self.test_settings):
            manager = BackupManager()
            now = datetime(2024, 1, 15, 14, 30)

            # Create current backup first
            manager.save_backups()

            # Call promotion manually
            manager._maybe_promote_to_daily(self.test_settings.CURRENT_BACKUP_PATH, now)  # pyright: ignore[reportPrivateUsage]

            # Check daily backup was created
            expected_daily = self.test_settings.DAILY_BACKUP_PATH / "2024-01-15.enc"
            assert expected_daily.exists()

    def test_maybe_promote_to_daily_respects_time_cutoff(self):
        """Test that daily backup is not overwritten within 10 minutes"""
        with patch("diary.utils.backup.settings", self.test_settings):
            manager = BackupManager()
            base_time = datetime.now()

            # Create current backup
            manager.save_backups()

            # Create first daily backup
            promoted = manager._maybe_promote_to_daily(  # pyright: ignore[reportPrivateUsage]
                self.test_settings.CURRENT_BACKUP_PATH, base_time
            )
            assert not promoted

            # Try to promote again 5 minutes later (should not overwrite)
            five_minutes_later = base_time + timedelta(minutes=5)
            promoted = manager._maybe_promote_to_daily(  # pyright: ignore[reportPrivateUsage]
                self.test_settings.CURRENT_BACKUP_PATH, five_minutes_later
            )
            assert not promoted

            fifteen_minutes_later = base_time + timedelta(minutes=30)
            promoted = manager._maybe_promote_to_daily(  # pyright: ignore[reportPrivateUsage]
                self.test_settings.CURRENT_BACKUP_PATH, fifteen_minutes_later
            )
            assert promoted

    def test_maybe_promote_to_weekly_on_monday(self):
        """Test that weekly backup is created on Monday"""
        with patch("diary.utils.backup.settings", self.test_settings):
            manager = BackupManager()

            # Create a test daily backup file
            monday_date = datetime(2024, 1, 15)  # This is a Monday
            daily_backup_path = self.test_settings.DAILY_BACKUP_PATH / "2024-01-15.enc"
            daily_backup_path.parent.mkdir(parents=True, exist_ok=True)
            _ = daily_backup_path.write_text("test backup content")

            # Promote to weekly
            _ = manager._maybe_promote_to_weekly(daily_backup_path, monday_date)  # pyright: ignore[reportPrivateUsage]

            # Check weekly backup was created (Monday Jan 15 2024 is week 3 in %W format)
            expected_weekly = self.test_settings.WEEKLY_BACKUP_PATH / "2024-W03.enc"
            assert expected_weekly.exists()
            assert expected_weekly.read_text() == "test backup content"

    def test_maybe_promote_to_weekly_not_on_monday(self):
        """Test that weekly backup is not created on non-Monday"""
        with patch("diary.utils.backup.settings", self.test_settings):
            manager = BackupManager()

            # Create a test daily backup file
            tuesday_date = datetime(2024, 1, 16)  # This is a Tuesday
            daily_backup_path = self.test_settings.DAILY_BACKUP_PATH / "2024-01-16.enc"
            daily_backup_path.parent.mkdir(parents=True, exist_ok=True)
            _ = daily_backup_path.write_text("test backup content")

            # Try to promote to weekly
            _ = manager._maybe_promote_to_weekly(daily_backup_path, tuesday_date)  # pyright: ignore[reportPrivateUsage]

            # Check no weekly backup was created
            weekly_files = list(self.test_settings.WEEKLY_BACKUP_PATH.glob("*.enc"))
            assert len(weekly_files) == 0

    def test_maybe_promote_to_monthly_first_week(self):
        """Test that monthly backup is created in first week of month"""
        with patch("diary.utils.backup.settings", self.test_settings):
            manager = BackupManager()

            # Create a test weekly backup file
            first_week_date = datetime(2024, 1, 3)  # 3rd day, within first week
            weekly_backup_path = self.test_settings.WEEKLY_BACKUP_PATH / "2024-W01.enc"
            weekly_backup_path.parent.mkdir(parents=True, exist_ok=True)
            _ = weekly_backup_path.write_text("test weekly backup")

            # Promote to monthly
            _ = manager._maybe_promote_to_monthly(weekly_backup_path, first_week_date)  # pyright: ignore[reportPrivateUsage]

            # Check monthly backup was created
            expected_monthly = self.test_settings.MONTLY_BACKUP_PATH / "2024-01.enc"
            assert expected_monthly.exists()
            assert expected_monthly.read_text() == "test weekly backup"

    def test_maybe_promote_to_monthly_not_first_week(self):
        """Test that monthly backup is not created outside first week"""
        with patch("diary.utils.backup.settings", self.test_settings):
            manager = BackupManager()

            # Create a test weekly backup file
            second_week_date = datetime(2024, 1, 10)  # 10th day, not in first week
            weekly_backup_path = self.test_settings.WEEKLY_BACKUP_PATH / "2024-W02.enc"
            weekly_backup_path.parent.mkdir(parents=True, exist_ok=True)
            _ = weekly_backup_path.write_text("test weekly backup")

            # Try to promote to monthly
            _ = manager._maybe_promote_to_monthly(weekly_backup_path, second_week_date)  # pyright: ignore[reportPrivateUsage]

            # Check no monthly backup was created
            monthly_files = list(self.test_settings.MONTLY_BACKUP_PATH.glob("*.enc"))
            assert len(monthly_files) == 0

    def test_rotate_daily_removes_old_backups(self):
        """Test that daily rotation removes backups older than 7 days"""
        with patch("diary.utils.backup.settings", self.test_settings):
            manager = BackupManager()
            now = datetime(2024, 1, 15)

            # Create some test daily backups
            self.test_settings.DAILY_BACKUP_PATH.mkdir(parents=True, exist_ok=True)

            # Create an old backup (10 days ago)
            old_backup = self.test_settings.DAILY_BACKUP_PATH / "2024-01-05.enc"
            _ = old_backup.write_text("old backup")

            # Create a recent backup (3 days ago)
            recent_backup = self.test_settings.DAILY_BACKUP_PATH / "2024-01-12.enc"
            _ = recent_backup.write_text("recent backup")

            # Run rotation
            manager._rotate_daily(now)  # pyright: ignore[reportPrivateUsage]

            # Check that old backup was removed and recent backup remains
            assert not old_backup.exists()
            assert recent_backup.exists()

    def test_rotate_weekly_removes_old_backups(self):
        """Test that weekly rotation removes backups older than 4 weeks"""
        with patch("diary.utils.backup.settings", self.test_settings):
            manager = BackupManager()
            now = datetime(2024, 2, 15)

            # Create some test weekly backups
            self.test_settings.WEEKLY_BACKUP_PATH.mkdir(parents=True, exist_ok=True)

            # Create an old backup (6 weeks ago)
            old_backup = self.test_settings.WEEKLY_BACKUP_PATH / "2023-52.enc"
            _ = old_backup.write_text("old weekly backup")

            # Create a recent backup (2 weeks ago)
            recent_backup = self.test_settings.WEEKLY_BACKUP_PATH / "2024-06.enc"
            _ = recent_backup.write_text("recent weekly backup")

            # Run rotation
            manager._rotate_weekly(now)  # pyright: ignore[reportPrivateUsage]

            # Check that old backup was removed and recent backup remains
            assert not old_backup.exists()
            assert recent_backup.exists()

    def test_rotate_monthly_removes_old_backups(self):
        """Test that monthly rotation removes backups older than 12 months"""
        with patch("diary.utils.backup.settings", self.test_settings):
            manager = BackupManager()
            now = datetime(2024, 6, 15)

            # Create some test monthly backups
            self.test_settings.MONTLY_BACKUP_PATH.mkdir(parents=True, exist_ok=True)

            # Create an old backup (15 months ago)
            old_backup = self.test_settings.MONTLY_BACKUP_PATH / "2023-02.enc"
            _ = old_backup.write_text("old monthly backup")

            # Create a recent backup (6 months ago)
            recent_backup = self.test_settings.MONTLY_BACKUP_PATH / "2023-12.enc"
            _ = recent_backup.write_text("recent monthly backup")

            # Run rotation
            manager._rotate_monthly(now)  # pyright: ignore[reportPrivateUsage]

            # Check that old backup was removed and recent backup remains
            assert not old_backup.exists()
            assert recent_backup.exists()

    def test_full_backup_workflow(self):
        """Test the complete backup workflow including promotions"""
        with patch("diary.utils.backup.settings", self.test_settings):
            manager = BackupManager()

            # Simulate a Monday in the first week of a month
            test_time = datetime(2024, 1, 1, 14, 30)  # Monday, Jan 1st

            with patch("diary.utils.backup.datetime") as mock_datetime:
                mock_datetime.now.return_value = test_time  # pyright: ignore[reportAny]
                mock_datetime.strptime = datetime.strptime
                mock_datetime.fromtimestamp = datetime.fromtimestamp

                # Run save_backups
                manager.save_backups()

                # Check current backup exists
                assert self.test_settings.CURRENT_BACKUP_PATH.exists()
                assert self.test_settings.CURRENT_BACKUP_PATH.is_file()

                # Check daily backup was created
                daily_backup = self.test_settings.DAILY_BACKUP_PATH / "2024-01-01.enc"
                assert daily_backup.exists()

    def test_backup_manager_constants(self):
        """Test that backup retention constants are set correctly"""
        manager = BackupManager()

        assert manager.KEEP_MONTHS == 12
        assert manager.KEEP_WEEKS == 4
        assert manager.KEEP_DAYS == 7

    def test_error_handling_in_rotation_methods(self):
        """Test that rotation methods handle errors gracefully"""
        with patch("diary.utils.backup.settings", self.test_settings):
            manager = BackupManager()

            # Create a malformed backup file that will cause parsing errors
            self.test_settings.DAILY_BACKUP_PATH.mkdir(parents=True, exist_ok=True)
            malformed_backup = self.test_settings.DAILY_BACKUP_PATH / "invalid-date.enc"
            _ = malformed_backup.write_text("malformed backup")

            # Test that rotation handles the error
            now = datetime(2024, 1, 15)
            try:
                manager._rotate_daily(now)  # pyright: ignore[reportPrivateUsage]
                # Should raise an exception for malformed filename
                assert False, "Expected exception for malformed filename"
            except (ValueError, OSError):
                # This is expected behavior
                pass

    def test_backup_file_content_integrity(self):
        """Test that backup files maintain content integrity"""
        with patch("diary.utils.backup.settings", self.test_settings):
            manager = BackupManager()

            # Modify the notebook file with specific content
            test_content = {
                "pages": [
                    {
                        "strokes": [{"points": [{"x": 100, "y": 200}]}],
                        "metadata": {"page_number": 1},
                    }
                ],
                "metadata": {"title": "Integrity Test", "version": "2.0"},
            }

            with open(self.test_settings.NOTEBOOK_FILE_PATH, "w") as f:
                json.dump(test_content, f)

            # Create backup
            manager.save_backups()

            # Verify backup content matches original
            with open(self.test_settings.NOTEBOOK_FILE_PATH, "r") as original:
                with open(self.test_settings.CURRENT_BACKUP_PATH, "r") as backup:
                    original_data = json.load(original)  # pyright: ignore[reportAny]
                    backup_data = json.load(backup)  # pyright: ignore[reportAny]
                    assert original_data == backup_data
