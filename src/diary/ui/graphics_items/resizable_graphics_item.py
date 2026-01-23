"""Shared resizing behavior for graphics items with corner handles."""

from abc import ABC, abstractmethod
from math import atan2, cos, degrees, radians, sin
from typing import override

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsSceneMouseEvent

from diary.models.page_element import PageElement

from .base_graphics_item import BaseGraphicsItem


class ResizableGraphicsItem(BaseGraphicsItem, ABC):
    """Base class that provides corner resize handles and interaction."""

    _HANDLE_SIZE: float = 8.0
    _HANDLE_HIT_SIZE: float = 16.0
    _ROTATE_HANDLE_SIZE: float = 8.0
    _ROTATE_HANDLE_HIT_SIZE: float = 18.0
    _ROTATE_HANDLE_OFFSET: float = 20.0
    _MIN_RESIZE_SIZE: float = 20.0
    _ROTATION_SNAP_DEGREES: float = 90.0
    _ROTATION_SNAP_THRESHOLD_DEGREES: float = 8.0

    def __init__(
        self, element: PageElement, parent: QGraphicsItem | None = None
    ) -> None:
        super().__init__(element, parent)
        self._resize_handle: str | None = None
        self._resize_start_rect: QRectF | None = None
        self._resize_start_scene_pos: QPointF | None = None
        self._rotation_active: bool = False
        self._rotate_start_angle: float | None = None
        self._rotate_start_rotation: float | None = None

    @abstractmethod
    def _get_current_size(self) -> tuple[float, float]:
        """Return the current width/height in local coordinates."""

    @abstractmethod
    def _apply_resize(
        self, new_size: tuple[float, float], new_scene_pos: QPointF
    ) -> None:
        """Apply size/position changes to the underlying element and item."""

    def _resize_min_size(self) -> float:
        """Return the minimum size for resizing."""
        return self._MIN_RESIZE_SIZE

    def _supports_rotation(self) -> bool:
        """Return True if the item supports rotation."""
        return False

    def _get_rotation(self) -> float:
        """Return the current rotation in degrees."""
        return 0.0

    def _set_rotation(self, rotation: float) -> None:
        """Set the rotation in degrees."""
        _ = rotation
        return None

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

    def _rotation_handle_position(self) -> QPointF:
        rect = self._resize_rect()
        return QPointF(rect.center().x(), rect.top() - self._ROTATE_HANDLE_OFFSET)

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

        if self._supports_rotation():
            rect = self._resize_rect()
            rotation_pos = self._rotation_handle_position()
            painter.drawLine(rect.center(), rotation_pos)
            rotation_rect = QRectF(
                rotation_pos.x() - self._ROTATE_HANDLE_SIZE / 2,
                rotation_pos.y() - self._ROTATE_HANDLE_SIZE / 2,
                self._ROTATE_HANDLE_SIZE,
                self._ROTATE_HANDLE_SIZE,
            )
            painter.drawEllipse(rotation_rect)

    def _get_handle_at_point(self, point: QPointF) -> str | None:
        """Return the resize handle at the point, if any."""
        if not self.isSelected():
            return None

        local_point = self._map_point_to_unrotated(point)
        if self._supports_rotation():
            rotation_pos = self._rotation_handle_position()
            rotation_rect = QRectF(
                rotation_pos.x() - self._ROTATE_HANDLE_HIT_SIZE / 2,
                rotation_pos.y() - self._ROTATE_HANDLE_HIT_SIZE / 2,
                self._ROTATE_HANDLE_HIT_SIZE,
                self._ROTATE_HANDLE_HIT_SIZE,
            )
            if rotation_rect.contains(local_point):
                return "rotate"

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
            if handle_rect.contains(local_point):
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
                if handle == "rotate":
                    if not self._supports_rotation():
                        return
                    start_rotation = self._get_rotation()
                    local_point = self._map_point_to_unrotated_with_rotation(
                        event.pos(), start_rotation
                    )
                    self._rotation_active = True
                    self._resize_start_rect = self._resize_rect()
                    self._rotate_start_angle = self._angle_to_point(local_point)
                    self._rotate_start_rotation = start_rotation
                    event.accept()
                    return
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
        if self._rotation_active:
            rotation = self._rotate_start_rotation
            if rotation is None:
                rotation = self._get_rotation()
            self._handle_rotation(
                self._map_point_to_unrotated_with_rotation(event.pos(), rotation)
            )
            event.accept()
            return
        if self._resize_handle:
            self._handle_resize(self._map_point_to_unrotated(event.pos()))
            event.accept()
            return

        super().mouseMoveEvent(event)

    @override
    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent | None) -> None:
        """Handle mouse release events."""
        if self._rotation_active:
            self._rotation_active = False
            self._rotate_start_angle = None
            self._rotate_start_rotation = None
            self._resize_start_rect = None
        if self._resize_handle:
            self._resize_handle = None
            self._resize_start_rect = None
            self._resize_start_scene_pos = None

        super().mouseReleaseEvent(event)

    def _handle_resize(self, current_pos: QPointF) -> None:
        """Handle resizing based on the active handle."""
        if not self._resize_handle or self._resize_start_rect is None:
            return

        start_rect = self._resize_start_rect
        start_scene_pos = self._resize_start_scene_pos or self.pos()
        min_size = self._resize_min_size()

        new_width = start_rect.width()
        new_height = start_rect.height()
        delta_x = 0.0
        delta_y = 0.0

        if self._resize_handle == "bottom-right":
            new_width = max(min_size, current_pos.x() - start_rect.left())
            new_height = max(min_size, current_pos.y() - start_rect.top())
        elif self._resize_handle == "top-left":
            new_width = max(min_size, start_rect.right() - current_pos.x())
            new_height = max(min_size, start_rect.bottom() - current_pos.y())
            delta_x = start_rect.width() - new_width
            delta_y = start_rect.height() - new_height
        elif self._resize_handle == "top-right":
            new_width = max(min_size, current_pos.x() - start_rect.left())
            new_height = max(min_size, start_rect.bottom() - current_pos.y())
            delta_y = start_rect.height() - new_height
        elif self._resize_handle == "bottom-left":
            new_width = max(min_size, start_rect.right() - current_pos.x())
            new_height = max(min_size, current_pos.y() - start_rect.top())
            delta_x = start_rect.width() - new_width

        new_scene_pos = QPointF(
            start_scene_pos.x() + delta_x, start_scene_pos.y() + delta_y
        )
        self._apply_resize((new_width, new_height), new_scene_pos)

    def _handle_rotation(self, current_pos: QPointF) -> None:
        if not self._rotation_active:
            return
        if self._rotate_start_angle is None or self._rotate_start_rotation is None:
            return
        if self._resize_start_rect is None:
            return

        center = self._resize_start_rect.center()
        current_angle = self._angle_to_point(current_pos, center)
        delta = current_angle - self._rotate_start_angle
        new_rotation = self._normalize_rotation(self._rotate_start_rotation + delta)
        snapped_rotation = self._snap_rotation(new_rotation)
        self._set_rotation(snapped_rotation)

    def _angle_to_point(self, point: QPointF, center: QPointF | None = None) -> float:
        center_point = center if center is not None else self._resize_rect().center()
        dx = point.x() - center_point.x()
        dy = point.y() - center_point.y()
        return degrees(atan2(dy, dx))

    def _normalize_rotation(self, rotation: float) -> float:
        return (rotation + 180.0) % 360.0 - 180.0

    def _snap_rotation(self, rotation: float) -> float:
        target = (
            round(rotation / self._ROTATION_SNAP_DEGREES)
            * self._ROTATION_SNAP_DEGREES
        )
        diff = self._normalize_rotation(rotation - target)
        if abs(diff) <= self._ROTATION_SNAP_THRESHOLD_DEGREES:
            return self._normalize_rotation(target)
        return rotation

    def _map_point_to_unrotated(self, point: QPointF) -> QPointF:
        if not self._supports_rotation():
            return point

        rotation = self._get_rotation()
        return self._map_point_to_unrotated_with_rotation(point, rotation)

    def _map_point_to_unrotated_with_rotation(
        self, point: QPointF, rotation: float
    ) -> QPointF:
        if not self._supports_rotation():
            return point

        if rotation == 0.0:
            return point

        center = self._resize_rect().center()
        angle = radians(-rotation)
        dx = point.x() - center.x()
        dy = point.y() - center.y()
        cos_angle = cos(angle)
        sin_angle = sin(angle)

        return QPointF(
            center.x() + dx * cos_angle - dy * sin_angle,
            center.y() + dx * sin_angle + dy * cos_angle,
        )
