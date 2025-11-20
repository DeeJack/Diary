"""Graphics item for rendering video elements using QGraphicsItem architecture"""

import logging
from typing import cast, override

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtMultimediaWidgets import QGraphicsVideoItem
from PyQt6.QtWidgets import (
    QGraphicsItem,
    QGraphicsSceneMouseEvent,
    QStyleOptionGraphicsItem,
    QWidget,
)

from diary.config import settings
from diary.models.elements import Video
from diary.models.point import Point

from .base_graphics_item import BaseGraphicsItem


class VideoGraphicsItem(BaseGraphicsItem):
    """Graphics item for rendering video elements with support for rotation and scaling"""

    def __init__(self, video_element: Video, parent: QGraphicsItem | None = None):
        super().__init__(video_element, parent)
        self._current_scale: float = 1.0
        self._logger: logging.Logger = logging.getLogger("VideoGraphicsItem")
        self._resize_handle: str
        self._resize_start_pos: QPointF
        self._resize_start_rect: QRectF

        # Widgets for playing video
        self._media_player: QMediaPlayer = QMediaPlayer()
        self._video_item: QGraphicsVideoItem = QGraphicsVideoItem()
        audio = QAudioOutput()
        self._media_player.setAudioOutput(audio)

        # Configure item flags for videos
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)

        self.setPos(self.video_element.position.x, self.video_element.position.y)

        # Enable transformations (use local coordinates)
        self.setTransformOriginPoint(
            self.video_element.width / 2, self.video_element.height / 2
        )

        # Load the video data
        self._load_video()

    @property
    def video_element(self) -> Video:
        """Get the video element"""
        return cast(Video, self._element)

    @override
    def _calculate_bounding_rect(self) -> QRectF:
        """Calculate the bounding rectangle for the video"""
        # Base rectangle in local coordinates (starting from 0,0)
        rect = QRectF(
            0,
            0,
            self.video_element.width,
            self.video_element.height,
        )

        # Add padding for selection highlighting and rotation
        padding = 10.0
        return rect.adjusted(-padding, -padding, padding, padding)

    @override
    def paint(
        self,
        painter: QPainter | None,
        option: QStyleOptionGraphicsItem | None,
        widget: QWidget | None = None,
    ) -> None:
        """Paint the video with support for rotation and scaling"""
        # if not painter:
        #     return

    def _draw_placeholder(self, painter: QPainter) -> None:
        """Draw a placeholder when video cannot be loaded"""
        rect = QRectF(
            0,
            0,
            self.video_element.width,
            self.video_element.height,
        )

        # Draw placeholder background
        painter.fillRect(rect, QColor(240, 240, 240))

        # Draw border
        painter.setPen(QPen(QColor(128, 128, 128), 2, Qt.PenStyle.DashLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(rect)

        # Draw "broken video" text
        painter.setPen(QPen(QColor(128, 128, 128)))
        _ = painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Video\nNot Available")

    def _draw_selection_highlight(self, painter: QPainter) -> None:
        """Draw selection highlight around the video"""
        rect = QRectF(
            -2,
            -2,
            self.video_element.width + 4,
            self.video_element.height + 4,
        )

        # Draw selection border
        selection_pen = QPen(QColor(0, 120, 255), 2, Qt.PenStyle.SolidLine)
        painter.setPen(selection_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(rect)

    def _draw_resize_handles(self, painter: QPainter) -> None:
        """Draw resize handles at the corners when selected"""
        handle_size = 8.0
        handle_color = QColor(0, 120, 255)

        # Calculate handle positions in local coordinates
        left = 0
        top = 0
        right = self.video_element.width
        bottom = self.video_element.height

        handle_positions = [
            QPointF(left, top),  # Top-left
            QPointF(right, top),  # Top-right
            QPointF(right, bottom),  # Bottom-right
            QPointF(left, bottom),  # Bottom-left
        ]

        painter.setPen(QPen(handle_color, 1))
        painter.setBrush(handle_color)

        for pos in handle_positions:
            handle_rect = QRectF(
                pos.x() - handle_size / 2,
                pos.y() - handle_size / 2,
                handle_size,
                handle_size,
            )
            painter.drawRect(handle_rect)

    def _load_video(self) -> None:
        """Load the video from the element data"""
        self._media_player.setVideoOutput(self._video_item)

    @override
    def _update_element_position(self, new_position: QPointF) -> None:
        """Update the video element's position when the graphics item moves"""
        if (
            0 <= new_position.x() <= settings.PAGE_WIDTH
            and 0 <= new_position.y() <= settings.PAGE_HEIGHT
        ):
            self.video_element.position = Point(new_position.x(), new_position.y(), 0)

    def set_size(self, width: float, height: float) -> None:
        """Update the video size"""
        self.video_element.width = width
        self.video_element.height = height

        # Update transform origin
        self.setTransformOriginPoint(width / 2, height / 2)
        self.invalidate_cache()

    def set_rotation(self, rotation: float) -> None:
        """Update the video rotation"""
        self.video_element.rotation = rotation
        self.update()

    def reload_video(self) -> None:
        """Reload the video from the element data"""
        self._load_video()
        self.update()

    def get_video_rect(self) -> QRectF:
        """Get the actual video rectangle in scene coordinates"""
        return QRectF(
            self.pos().x(),
            self.pos().y(),
            self.video_element.width,
            self.video_element.height,
        )

    def intersects_point(self, point: QPointF, radius: float = 5.0) -> bool:
        """Check if the video intersects with a point within the given radius"""
        # Convert point to local coordinates
        local_point = self.mapFromScene(point)
        local_rect = QRectF(0, 0, self.video_element.width, self.video_element.height)
        expanded_rect = local_rect.adjusted(-radius, -radius, radius, radius)
        return expanded_rect.contains(local_point)

    def contains_point(self, point: QPointF) -> bool:
        """Check if the point is inside the video"""
        # Convert point to local coordinates and check against local rect
        local_point = self.mapFromScene(point)
        local_rect = QRectF(0, 0, self.video_element.width, self.video_element.height)
        return local_rect.contains(local_point)

    def get_handle_at_point(self, point: QPointF) -> str | None:
        """Get the resize handle at the given point, if any"""
        if not self.isSelected():
            return None

        handle_size = 16.0
        left = 0
        top = 0
        right = self.video_element.width
        bottom = self.video_element.height

        handles = {
            "top-left": QRectF(
                left - handle_size / 2, top - handle_size / 2, handle_size, handle_size
            ),
            "top-right": QRectF(
                right - handle_size / 2, top - handle_size / 2, handle_size, handle_size
            ),
            "bottom-right": QRectF(
                right - handle_size / 2,
                bottom - handle_size / 2,
                handle_size,
                handle_size,
            ),
            "bottom-left": QRectF(
                left - handle_size / 2,
                bottom - handle_size / 2,
                handle_size,
                handle_size,
            ),
        }

        for handle_name, handle_rect in handles.items():
            if handle_rect.contains(point):
                return handle_name

        return None

    @override
    def type(self) -> int:
        """Return unique type identifier for video items"""
        return hash("VideoGraphicsItem") & 0x7FFFFFFF

    def clone(self) -> "VideoGraphicsItem":
        """Create a copy of this video graphics item"""
        new_video = Video(
            position=Point(
                self.video_element.position.x,
                self.video_element.position.y,
                self.video_element.position.pressure,
            ),
            width=self.video_element.width,
            height=self.video_element.height,
            video_path=self.video_element.video_path,
            video_data=self.video_element.video_data,
            rotation=self.video_element.rotation,
        )
        return VideoGraphicsItem(new_video)

    @override
    def mousePressEvent(self, event: QGraphicsSceneMouseEvent | None) -> None:
        """Handle mouse press events for resizing"""
        if not event:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self.get_handle_at_point(event.pos())
            if handle:
                # Store resize start state
                self._resize_handle = handle
                self._resize_start_pos = event.pos()
                self._resize_start_rect = QRectF(
                    0, 0, self.video_element.width, self.video_element.height
                )
                event.accept()
                return

        super().mousePressEvent(event)

    @override
    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent | None) -> None:
        """Handle mouse move events for resizing"""
        if not event:
            return
        if hasattr(self, "_resize_handle") and self._resize_handle:
            self._logger.debug("Resizing: %s", event.pos())
            self._handle_resize(event.pos())
            event.accept()
            return

        super().mouseMoveEvent(event)

    @override
    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent | None) -> None:
        """Handle mouse release events"""
        if hasattr(self, "_resize_handle"):
            delattr(self, "_resize_handle")
            if hasattr(self, "_resize_start_pos"):
                delattr(self, "_resize_start_pos")
            if hasattr(self, "_resize_start_rect"):
                delattr(self, "_resize_start_rect")

        super().mouseReleaseEvent(event)

    def _handle_resize(self, current_pos: QPointF) -> None:
        """Handle video resizing based on handle movement"""
        if not hasattr(self, "_resize_handle") or not hasattr(
            self, "_resize_start_rect"
        ):
            return

        start_rect = self._resize_start_rect
        handle = self._resize_handle

        # Calculate new dimensions based on handle
        if handle == "bottom-right":
            new_width = max(20, current_pos.x())
            new_height = max(20, current_pos.y())
            self.set_size(new_width, new_height)

        elif handle == "top-left":
            new_width = max(20, start_rect.width() - current_pos.x())
            new_height = max(20, start_rect.height() - current_pos.y())

            # Update position and size for top-left handle
            # Calculate new scene position based on the offset
            offset_x = current_pos.x()
            offset_y = current_pos.y()
            current_scene_pos = self.pos()
            new_scene_pos = QPointF(
                current_scene_pos.x() + offset_x, current_scene_pos.y() + offset_y
            )

            self.video_element.position = Point(
                new_scene_pos.x(),
                new_scene_pos.y(),
                self.video_element.position.pressure,
            )
            self.setPos(new_scene_pos)
            self.set_size(new_width, new_height)

        self.invalidate_cache()
