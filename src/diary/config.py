"""
Contains the configuration options for the Diary application
"""

import json
import logging
from enum import Enum
from pathlib import Path

from pydantic import ValidationError
from pydantic_settings import BaseSettings

from diary.ui.widgets.tool_selector import Tool

SETTINGS_FILE_PATH = "data/config.json"


class Settings(BaseSettings):
    """Settings class for the Diary application"""

    DATA_DIR_PATH: Path = Path("data")
    NOTEBOOK_FILE_PATH: Path = DATA_DIR_PATH / Path("notebook.enc")
    BACKUP_DIR_PATH: Path = DATA_DIR_PATH / Path("backup")
    DAILY_BACKUP_PATH: Path = BACKUP_DIR_PATH / Path("daily")
    WEEKLY_BACKUP_PATH: Path = BACKUP_DIR_PATH / Path("weekly")
    MONTLY_BACKUP_PATH: Path = BACKUP_DIR_PATH / Path("monthly")
    CURRENT_BACKUP_PATH: Path = BACKUP_DIR_PATH / "current.enc"
    LOGGING_DIR_PATH: Path = DATA_DIR_PATH / "logging"

    # Page
    RENDERING_SCALE: float = 4
    PAGE_WIDTH: int = 800
    PAGE_HEIGHT: int = 1100
    PAGE_LINES_SPACING: int = 35
    PAGE_LINES_MARGIN: int = 5
    PAGE_BETWEEN_SPACING: int = 10
    USE_PRESSURE: bool = False
    PREFERRED_THICKNESS: float = 1.0
    PAGE_BACKGROUND_COLOR: str = "#E0E0E0"
    PAGE_LINES_COLOR: str = "#DDCDC4"

    AUTOSAVE_NOTEBOOK_TIMEOUT: int = 120  # in seconds
    CURRENT_TOOL: Tool = Tool.PEN
    CURRENT_WIDTH: float = 2.0
    CURRENT_COLOR: str = "black"
    TOUCH_ENABLED: bool = False
    MOUSE_ENABLED: bool = True

    class SERIALIZATION_KEYS(Enum):
        """Value used as the keys for the serialization"""

        ELEMENT_ID = "id"
        ELEMENT_TYPE = "type"
        POSITION = "pos"
        PAGES = "pages"
        CREATED_AT = "created_at"
        ELEMENTS = "elements"
        TYPE_STROKE = "stroke"
        TYPE_IMAGE = "image"
        TYPE_VOICE = "voice"
        TYPE_TEXT = "text"
        METADATA = "metadata"
        POINTS = "points"
        COLOR = "color"
        THICKNESS = "thickness"
        TOOL = "tool"
        WIDTH = "width"
        HEIGHT = "height"
        PATH = "path"
        DATA = "data"
        ROTATION = "rotation"
        TRANSCRIPT = "transcript"
        DURATION = "duration"
        TEXT = "text"
        SIZE_PX = "size_px"

    @classmethod
    def load_from_file(cls, path: Path) -> "Settings":
        """Loads settings from a JSON file."""
        if not path.exists():
            return cls()  # Return default

        try:
            with open(path, "r") as f:
                data = json.load(f)
            return cls(**data)
        except (json.JSONDecodeError, ValidationError) as e:
            logging.getLogger("Config").error("Error loading settings: %s", e)
            return cls()  # Return defaults

    def save_to_file(self, path: Path):
        """Saves settings to JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(path, "w") as f:
                _ = f.write(self.model_dump_json(indent=2))
        except Exception as e:
            logging.getLogger("Config").error("Error saving settings: %s", e)


settings = Settings.load_from_file(Path(SETTINGS_FILE_PATH))
