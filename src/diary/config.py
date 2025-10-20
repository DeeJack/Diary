"""
Contains the configuration options for the Diary application
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings class for the Diary application"""

    model_config: SettingsConfigDict = {  # pyright: ignore[reportIncompatibleVariableOverride]
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }

    DATA_DIR_PATH: Path = Path("data")
    NOTEBOOK_FILE_PATH: Path = DATA_DIR_PATH / Path("notebook.json")
    BACKUP_DIR_PATH: Path = DATA_DIR_PATH / Path("backup")
    DAILY_BACKUP_PATH: Path = BACKUP_DIR_PATH / Path("daily")
    WEEKLY_BACKUP_PATH: Path = BACKUP_DIR_PATH / Path("weekly")
    MONTLY_BACKUP_PATH: Path = BACKUP_DIR_PATH / Path("monthly")
    CURRENT_BACKUP_PATH: Path = BACKUP_DIR_PATH / "current.enc"
    LOGGING_DIR_PATH: Path = DATA_DIR_PATH / "logging"

    # Page
    PAGE_WIDTH: int = 800
    PAGE_HEIGHT: int = 1100
    PAGE_LINES_SPACING: int = 35
    PAGE_LINES_MARING: int = 5
    PAGE_BETWEEN_SPACING: int = 10

    AUTOSAVE_NOTEBOOK_TIMEOUT: int = 120  # in seconds


settings = Settings()
