"""Backup management system for the Diary"""

from datetime import timedelta, datetime
from pathlib import Path
import shutil

from diary.config import settings


class BackupManager:
    KEEP_MONTHS: int = 12
    KEEP_WEEKS: int = 4
    KEEP_DAYS: int = 7

    def __init__(self):
        settings.CURRENT_BACKUP_PATH.parent.mkdir(parents=True, exist_ok=True)
        settings.DAILY_BACKUP_PATH.mkdir(parents=True, exist_ok=True)
        settings.WEEKLY_BACKUP_PATH.mkdir(parents=True, exist_ok=True)
        settings.MONTLY_BACKUP_PATH.mkdir(parents=True, exist_ok=True)

    def save_backups(self):
        _ = shutil.copy2(settings.NOTEBOOK_FILE_PATH, settings.CURRENT_BACKUP_PATH)

        now = datetime.now()
        _ = self._maybe_promote_to_daily(settings.CURRENT_BACKUP_PATH, now)
        _ = self._maybe_promote_to_weekly(settings.CURRENT_BACKUP_PATH, now)
        _ = self._maybe_promote_to_monthly(settings.CURRENT_BACKUP_PATH, now)

        self._rotate_daily(now)
        self._rotate_weekly(now)
        self._rotate_monthly(now)

    def _rotate_daily(self, now: datetime):
        """Keep only daily backups from last 7 days"""
        cutoff_date = now - timedelta(days=7)

        for backup_file in settings.DAILY_BACKUP_PATH.glob("*.enc"):
            try:
                date_str = backup_file.stem  # YYYY-MM-DD
                backup_date = datetime.strptime(date_str, "%Y-%m-%d")

                if backup_date < cutoff_date:
                    _ = self._maybe_promote_to_weekly(backup_file, backup_date)
                    backup_file.unlink()
            except (ValueError, OSError) as e:
                raise e

    def _rotate_weekly(self, now: datetime):
        """Keep only weekly backups from last 4 weeks"""
        cutoff_date = now - timedelta(weeks=self.KEEP_WEEKS)

        for backup_file in settings.WEEKLY_BACKUP_PATH.glob("*.enc"):
            try:
                parts = backup_file.stem.split("-")
                year = parts[0]
                week = parts[1]
                backup_date = datetime.strptime(f"{year}-W{week}-1", "%Y-W%W-%w")

                if backup_date < cutoff_date:
                    _ = self._maybe_promote_to_monthly(backup_file, backup_date)
                    backup_file.unlink()
            except (ValueError, OSError) as e:
                raise e

    def _rotate_monthly(self, now: datetime):
        """Keep only monthly backups from last 12 months"""
        cutoff_date = now - timedelta(days=30 * self.KEEP_MONTHS)

        for backup_file in settings.MONTLY_BACKUP_PATH.glob("*.enc"):
            try:
                date_str = backup_file.stem + "-01"  # YYYY-MM + -DD
                backup_date = datetime.strptime(date_str, "%Y-%m-%d")

                if backup_date < cutoff_date:
                    backup_file.unlink()
            except (ValueError, OSError) as e:
                raise e

    def _maybe_promote_to_daily(self, backup_file: Path, now: datetime):
        """Copy the current backup to the daily backup if it doesn't exists, or is older than 10 minutes"""
        daily_str = now.strftime("%Y-%m-%d.enc")
        daily_path = settings.DAILY_BACKUP_PATH / daily_str

        if not daily_path.exists():
            _ = shutil.copy2(backup_file, daily_path)
            return True

        last_daily_date = datetime.fromtimestamp(daily_path.stat().st_mtime)
        cutoff_date = last_daily_date + timedelta(minutes=10)
        if now > cutoff_date:
            _ = shutil.copy2(backup_file, daily_path)
            return True
        return False

    def _maybe_promote_to_weekly(self, daily_backup_file: Path, backup_date: datetime):
        """Promote daily to weekly if it's a monday"""
        if backup_date.weekday() == 0:
            weekly_str = backup_date.strftime("%Y-W%W.enc")
            weekly_path = settings.WEEKLY_BACKUP_PATH / weekly_str

            if not weekly_path.exists():
                _ = shutil.copy2(daily_backup_file, weekly_path)
                return True
        return False

    def _maybe_promote_to_monthly(
        self, weekly_backup_file: Path, backup_date: datetime
    ):
        """Promote weekly to monthly if it's the first week"""
        if backup_date.day <= 7:
            montly_str = backup_date.strftime("%Y-%m.enc")
            monthly_path = settings.MONTLY_BACKUP_PATH / montly_str

            if not monthly_path.exists():
                _ = shutil.copy2(weekly_backup_file, monthly_path)
                return True
        return False
