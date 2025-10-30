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
    """Get the cursor corresponding to a Tool"""
    cursor: Qt.CursorShape
    match tool:
        case Tool.TEXT:
            cursor = Qt.CursorShape.IBeamCursor
        case Tool.PEN:
            cursor = Qt.CursorShape.CrossCursor
        case Tool.ERASER:
            cursor = Qt.CursorShape.ForbiddenCursor
        case Tool.DRAG:
            cursor = Qt.CursorShape.OpenHandCursor
        case Tool.IMAGE:
            cursor = Qt.CursorShape.CrossCursor
        case Tool.AUDIO:
            cursor = Qt.CursorShape.CrossCursor
        case Tool.SELECTION:
            cursor = Qt.CursorShape.ArrowCursor
    return cursor
