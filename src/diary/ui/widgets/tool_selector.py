"""Enum with the tools available in the application"""

from enum import Enum

from PyQt6.QtCore import Qt


class Tool(Enum):
    """Enum with the tools available in the application"""

    PEN = "PEN"
    ERASER = "ERASER"
    TEXT = "TEXT"
    DRAG = "DRAG"
    IMAGE = "IMAGE"
    AUDIO = "AUDIO"
    SELECTION = "SELECTION"


def get_cursor_from_tool(tool: Tool) -> Qt.CursorShape:
    match tool:
        case Tool.TEXT:
            return Qt.CursorShape.IBeamCursor
        case Tool.PEN:
            return Qt.CursorShape.CrossCursor
        case Tool.ERASER:
            return Qt.CursorShape.ForbiddenCursor
        case Tool.DRAG:
            return Qt.CursorShape.OpenHandCursor
        case Tool.IMAGE:
            return Qt.CursorShape.CrossCursor
        case Tool.AUDIO:
            return Qt.CursorShape.CrossCursor
        case Tool.SELECTION:
            return Qt.CursorShape.ArrowCursor
