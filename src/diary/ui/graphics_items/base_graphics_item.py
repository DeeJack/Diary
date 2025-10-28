"""Base graphics item class providing common functionality for diary elements"""

from abc import ABC, ABCMeta, abstractmethod
from typing import Any

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import (
    QGraphicsItem,
    QGraphicsSceneHoverEvent,
    QStyleOptionGraphicsItem,
    QWidget,
)
from typing_extensions import override

from diary.models.page_element import PageElement

QGraphicsItemMeta = type(QGraphicsItem)


class GraphicsItemABCMeta(ABCMeta, QGraphicsItemMeta):
    """To solve a pyright warning"""


class BaseGraphicsItem(QGraphicsItem, ABC, metaclass=GraphicsItemABCMeta):
    """Base class for all diary element graphics items"""

    def __init__(self, element: PageElement, parent: QGraphicsItem | None = None):
        super().__init__(parent)
        self._element: PageElement = element
        self._cached_bounding_rect: QRectF | None = None

        # Enable caching, movable objects, and hover events
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setAcceptHoverEvents(True)

    @property
    def element(self) -> PageElement:
        """Get the underlying page element"""
        return self._element

    @element.setter
    def element(self, value: PageElement) -> None:
        """Set the underlying page element and invalidate cache"""
        self._element = value
        self._cached_bounding_rect = None
        self.prepareGeometryChange()
        self.update()

    @override
    def boundingRect(self) -> QRectF:
        """Return the bounding rectangle of this item"""
        if self._cached_bounding_rect is None:
            self._cached_bounding_rect = self._calculate_bounding_rect()
        return self._cached_bounding_rect

    @abstractmethod
    def _calculate_bounding_rect(self) -> QRectF:
        """Calculate the bounding rectangle for this element"""

    @override
    @abstractmethod
    def paint(
        self,
        painter: QPainter | None,
        option: QStyleOptionGraphicsItem | None,
        widget: QWidget | None = None,
    ) -> None:
        """Paint this graphics item"""

    def invalidate_cache(self) -> None:
        """Invalidate cached bounding rect and trigger update"""
        self._cached_bounding_rect = None
        self.prepareGeometryChange()
        self.update()

    def configure_painter_quality(self, painter: QPainter) -> None:
        """Configure painter for high-quality rendering"""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

    @override
    def type(self) -> int:
        """Return a unique type identifier for this item"""
        # Use hash of class name for unique type identification
        return hash(self.__class__.__name__) & 0x7FFFFFFF

    @override
    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any) -> Any:
        """Handle item changes (position, selection, etc.)"""
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            # Update the element's position when the graphics item moves
            self._update_element_position(value)
        elif change == QGraphicsItem.GraphicsItemChange.ItemSelectedChange:
            # Handle selection state changes
            self._handle_selection_change(value)

        return super().itemChange(change, value)

    def _update_element_position(self, new_position: Any) -> None:
        """Update the underlying element's position (override in subclasses)"""

    def _handle_selection_change(self, selected: bool) -> None:
        """Handle selection state change"""
        if selected:
            # Highlight selected items
            self.setZValue(1.0)  # Bring to front
        else:
            self.setZValue(0.0)  # Normal z-order

    @override
    def hoverEnterEvent(self, event: QGraphicsSceneHoverEvent | None) -> None:
        """Handle hover enter events"""
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        super().hoverEnterEvent(event)

    @override
    def hoverLeaveEvent(self, event: QGraphicsSceneHoverEvent | None) -> None:
        """Handle hover leave events"""
        self.unsetCursor()
        super().hoverLeaveEvent(event)

    @override
    def __str__(self) -> str:
        """String representation for debugging"""
        return f"{self.__class__.__name__}(element_id={self._element.element_id})"

    @override
    def __repr__(self) -> str:
        """Detailed representation for debugging"""
        return (
            f"{self.__class__.__name__}("
            f"element_id={self._element.element_id}, "
            f"element_type={self._element.element_type}, "
            f"pos={self.pos()}, "
            f"bounds={self.boundingRect()})"
        )
