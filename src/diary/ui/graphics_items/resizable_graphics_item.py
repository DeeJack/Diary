"""Shared resizing behavior for graphics items with corner handles."""

from abc import ABC, abstractmethod
from typing import override

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QPainter, QPen, QColor
from PyQt6.QtWidgets import QGraphicsSceneMouseEvent

from .base_graphics_item import BaseGraphicsItem


class ResizableGraphicsItem(BaseGraphicsItem, ABC):
    """Base class that provides corner resize handles and interaction."""

    _HANDLE_SIZE = 8.0
    _HANDLE_HIT_SIZE = 16.0
    _MIN_RESIZE_SIZE = 20.0

    def __init__(self, element, parent=None) -> None:
        super().__init__(element, parent)
        self._resize_handle: str | None = None
        self._resize_start_rect: QRectF | None = None
        self._resize_start_scene_pos: QPointF | None = None

    @abstractmethod
    def _get_current_size(self) -> tuple[float, float]:
        """Return the current width/height in local coordinates."""

    @abstractmethod
    def _apply_resize(self, new_size: tuple[float, float], new_scene_pos: QPointF) -> None:
        """Apply size/position changes to the underlying element and item."""

    def _resize_min_size(self) -> float:
        """Return the minimum size for resizing."""
        return self._MIN_RESIZE_SIZE

    def _resize_rect(self) -> QRectF:
        width, height = self._get_current_size()
        return QRectF(0, 0, width, height)

    def _resize_handle_positions(self) -> dict[str, QPointF]:
        rect = self._resize_rect()
        left = rect.left()
        top = rect.top()
        right = rect.right()
        bottom = rect.bottom()

        return {
            "top-left": QPointF(left, top),
            "top-right": QPointF(right, top),
            "bottom-right": QPointF(right, bottom),
            "bottom-left": QPointF(left, bottom),
        }

    def _draw_resize_handles(self, painter: QPainter) -> None:
        """Draw resize handles at the corners when selected."""
        handle_color = QColor(0, 120, 255)
        painter.setPen(QPen(handle_color, 1))
        painter.setBrush(handle_color)

        for pos in self._resize_handle_positions().values():
            handle_rect = QRectF(
                pos.x() - self._HANDLE_SIZE / 2,
                pos.y() - self._HANDLE_SIZE / 2,
                self._HANDLE_SIZE,
                self._HANDLE_SIZE,
            )
            painter.drawRect(handle_rect)

    def _get_handle_at_point(self, point: QPointF) -> str | None:
        """Return the resize handle at the point, if any."""
        if not self.isSelected():
            return None

        handles = {
            name: QRectF(
                pos.x() - self._HANDLE_HIT_SIZE / 2,
                pos.y() - self._HANDLE_HIT_SIZE / 2,
                self._HANDLE_HIT_SIZE,
                self._HANDLE_HIT_SIZE,
            )
            for name, pos in self._resize_handle_positions().items()
        }

        for handle_name, handle_rect in handles.items():
            if handle_rect.contains(point):
                return handle_name

        return None

    @override
    def mousePressEvent(self, event: QGraphicsSceneMouseEvent | None) -> None:
        """Handle mouse press events for resizing."""
        if not event:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self._get_handle_at_point(event.pos())
            if handle:
                self._resize_handle = handle
                self._resize_start_rect = self._resize_rect()
                self._resize_start_scene_pos = self.pos()
                event.accept()
                return

        super().mousePressEvent(event)

    @override
    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent | None) -> None:
        """Handle mouse move events for resizing."""
        if not event:
            return
        if self._resize_handle:
            self._handle_resize(event.pos())
            event.accept()
            return

        super().mouseMoveEvent(event)

    @override
    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent | None) -> None:
        """Handle mouse release events."""
        if self._resize_handle:
            self._resize_handle = None
            self._resize_start_rect = None
            self._resize_start_scene_pos = None

        super().mouseReleaseEvent(event)

    def _handle_resize(self, current_pos: QPointF) -> None:
        """Handle resizing based on the active handle."""
        if not self._resize_handle or not self._resize_start_rect:
            return

        start_rect = self._resize_start_rect
        start_scene_pos = self._resize_start_scene_pos or self.pos()
        min_size = self._resize_min_size()

        new_width = start_rect.width()
        new_height = start_rect.height()
        delta_x = 0.0
        delta_y = 0.0

        if self._resize_handle == "bottom-right":
            new_width = max(min_size, current_pos.x())
            new_height = max(min_size, current_pos.y())
        elif self._resize_handle == "top-left":
            new_width = max(min_size, start_rect.width() - current_pos.x())
            new_height = max(min_size, start_rect.height() - current_pos.y())
            delta_x = start_rect.width() - new_width
            delta_y = start_rect.height() - new_height
        elif self._resize_handle == "top-right":
            new_width = max(min_size, current_pos.x())
            new_height = max(min_size, start_rect.height() - current_pos.y())
            delta_y = start_rect.height() - new_height
        elif self._resize_handle == "bottom-left":
            new_width = max(min_size, start_rect.width() - current_pos.x())
            new_height = max(min_size, current_pos.y())
            delta_x = start_rect.width() - new_width

        new_scene_pos = QPointF(
            start_scene_pos.x() + delta_x, start_scene_pos.y() + delta_y
        )
        self._apply_resize((new_width, new_height), new_scene_pos)
