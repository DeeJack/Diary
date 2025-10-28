"""
Contains the configuration options for the Diary application
"""

from enum import Enum
from pathlib import Path

from pydantic_settings import BaseSettings
from PyQt6.QtGui import QColor

from diary.ui.widgets.tool_selector import Tool


class Settings(BaseSettings):
    """Settings class for the Diary application"""

    model_config = {  # pyright: ignore[reportUnannotatedClassAttribute]
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }

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

    AUTOSAVE_NOTEBOOK_TIMEOUT: int = 120  # in seconds
    CURRENT_TOOL: Tool = Tool.PEN
    CURRENT_WIDTH: float = 2.0
    CURRENT_COLOR: QColor = QColor("black")
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


settings = Settings()
