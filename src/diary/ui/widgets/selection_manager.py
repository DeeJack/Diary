from enum import Enum
import logging

from PyQt6.QtCore import QPointF, QRectF

from diary.models import Page, Point
from diary.ui.adapters import adapter_registry


class HandleType(Enum):
    TOP_LEFT = 0
    TOP_RIGHT = 1
    BOTTOM_LEFT = 2
    BOTTOM_RIGHT = 3


class SelectionRect:
    """Selection handles rect"""

    def __init__(self, position: QPointF, type: HandleType):
        self.position: QPointF = position
        self.type: HandleType = type
        self.size: float = 8.0

    def rect(self) -> QRectF:
        """Get the rectangle bounds of this handle"""
        half_size = self.size / 2
        return QRectF(
            self.position.x() - half_size,
            self.position.y() - half_size,
            self.size,
            self.size,
        )

    def contains(self, point: QPointF) -> bool:
        """Check if a point is within this handle"""
        return self.rect().contains(point)


class SelectionManager:
    """Handles selection, moving, and resizing objects"""

    def __init__(self, page: Page):
        self.page: Page = page
        self.logger: logging.Logger = logging.getLogger("SelectionManager")

    def _get_element_at(self, position: Point):
        for element in self.page.elements:
