"""Base graphics item class providing common functionality for diary elements"""

from abc import ABC, ABCMeta, abstractmethod
from typing import Any, override

from PyQt6 import QtGui
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import (
    QGraphicsItem,
    QStyleOptionGraphicsItem,
    QWidget,
)

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

    def _update_element_position(self, new_position: QPointF) -> None:
        """Update the underlying element's position (override in subclasses)"""

    def _handle_selection_change(self, _: bool) -> None:
        """Handle selection state change"""
        # if selected:
        #   self.setZValue(2.0)  # Bring to front

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

    @override
    def keyPressEvent(self, event: QtGui.QKeyEvent | None) -> None:
        """On key pressed (delete element)"""
        if not event:
            return None
        if self.isSelected() and event.key() == Qt.Key.Key_Cancel:
            self.hide()
        return super().keyPressEvent(event)
