"""
Contains the configuration options for the Diary application
"""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Settings class for the Diary application"""

    class Config:
        """Where to load configs from"""

        env_file: str = ".env"
        env_file_encoding: str = "utf-8"

    NOTEBOOK_FILE_PATH: Path = Path("data/notebook.json")

    # Page
    PAGE_WIDTH: int = 800
    PAGE_HEIGHT: int = 1100
    PAGE_LINES_SPACING: int = 35
    PAGE_LINES_MARING: int = 5
    PAGE_BETWEEN_SPACING: int = 10


settings = Settings()
