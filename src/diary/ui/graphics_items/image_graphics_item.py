"""Graphics item for rendering image elements using QGraphicsItem architecture"""

import logging
import math
from typing import cast, override

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QColor,
    QPainter,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem, QWidget

from diary.config import settings
from diary.models.elements.image import Image
from diary.models.point import Point

from .resizable_graphics_item import ResizableGraphicsItem


class ImageGraphicsItem(ResizableGraphicsItem):
    """Graphics item for rendering image elements with support for rotation and scaling"""

    def __init__(self, image_element: Image, parent: QGraphicsItem | None = None):
        super().__init__(image_element, parent)
        self._pixmap: QPixmap | None = None
        self._scaled_pixmap: QPixmap | None = None
        self._current_scale: float = 1.0
        self._logger: logging.Logger = logging.getLogger("ImageGraphicsItem")
        # Configure item flags for images
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)

        self.setPos(self.image_element.position.x, self.image_element.position.y)

        # Enable transformations (use local coordinates)
        self.setTransformOriginPoint(
            self.image_element.width / 2, self.image_element.height / 2
        )

        # Load the image data
        self._load_image()

    @property
    def image_element(self) -> Image:
        """Get the image element"""
        return cast(Image, self._element)

    @override
    def _calculate_bounding_rect(self) -> QRectF:
        """Calculate the bounding rectangle for the image"""
        rect = QRectF(0, 0, self.image_element.width, self.image_element.height)
        rotated_rect = self._rotated_bounds(rect, self.image_element.rotation)

        padding = 10.0
        rotate_padding = (
            self._ROTATE_HANDLE_OFFSET + self._ROTATE_HANDLE_SIZE
            if self._supports_rotation()
            else 0.0
        )
        return rotated_rect.adjusted(
            -padding,
            -(padding + rotate_padding),
            padding,
            padding,
        )

    def _rotated_bounds(self, rect: QRectF, rotation: float) -> QRectF:
        if rotation == 0.0:
            return QRectF(rect)

        center = rect.center()
        angle = math.radians(rotation)
        cos_angle = math.cos(angle)
        sin_angle = math.sin(angle)
        corners = (
            rect.topLeft(),
            rect.topRight(),
            rect.bottomLeft(),
            rect.bottomRight(),
        )

        xs: list[float] = []
        ys: list[float] = []
        for corner in corners:
            dx = corner.x() - center.x()
            dy = corner.y() - center.y()
            rotated_x = center.x() + dx * cos_angle - dy * sin_angle
            rotated_y = center.y() + dx * sin_angle + dy * cos_angle
            xs.append(rotated_x)
            ys.append(rotated_y)

        return QRectF(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))

    @override
    def paint(
        self,
        painter: QPainter | None,
        option: QStyleOptionGraphicsItem | None,
        widget: QWidget | None = None,
    ) -> None:
        """Paint the image with support for rotation and scaling"""
        if not painter:
            return
        if not self._pixmap or self._pixmap.isNull():
            self._draw_placeholder(painter)
            return

        # Configure painter for high-quality image rendering
        self.configure_painter_quality(painter)

        # Draw selection highlight if selected
        if self.isSelected():
            painter.save()
            if self.image_element.rotation != 0.0:
                center_x = self.image_element.width / 2
                center_y = self.image_element.height / 2
                painter.translate(center_x, center_y)
                painter.rotate(self.image_element.rotation)
                painter.translate(-center_x, -center_y)
            self._draw_selection_highlight(painter)
            painter.restore()

        # Save painter state for transformations
        painter.save()

        # Apply rotation if specified
        if self.image_element.rotation != 0.0:
            center_x = self.image_element.width / 2
            center_y = self.image_element.height / 2
            painter.translate(center_x, center_y)
            painter.rotate(self.image_element.rotation)
            painter.translate(-center_x, -center_y)

        # Draw the image in local coordinates
        target_rect = QRectF(
            0,
            0,
            self.image_element.width,
            self.image_element.height,
        )

        # Use scaled pixmap if available for better performance
        pixmap_to_draw = self._scaled_pixmap if self._scaled_pixmap else self._pixmap
        painter.drawPixmap(target_rect, pixmap_to_draw, pixmap_to_draw.rect().toRectF())

        # Restore painter state
        painter.restore()

        # Draw resize handles if selected
        if self.isSelected():
            painter.save()
            if self.image_element.rotation != 0.0:
                center_x = self.image_element.width / 2
                center_y = self.image_element.height / 2
                painter.translate(center_x, center_y)
                painter.rotate(self.image_element.rotation)
                painter.translate(-center_x, -center_y)
            self._draw_resize_handles(painter)
            painter.restore()

    def _draw_placeholder(self, painter: QPainter) -> None:
        """Draw a placeholder when image cannot be loaded"""
        rect = QRectF(
            0,
            0,
            self.image_element.width,
            self.image_element.height,
        )

        # Draw placeholder background
        painter.fillRect(rect, QColor(240, 240, 240))

        # Draw border
        painter.setPen(QPen(QColor(128, 128, 128), 2, Qt.PenStyle.DashLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(rect)

        # Draw "broken image" text
        painter.setPen(QPen(QColor(128, 128, 128)))
        _ = painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Image\nNot Available")

    def _draw_selection_highlight(self, painter: QPainter) -> None:
        """Draw selection highlight around the image"""
        rect = QRectF(
            -2,
            -2,
            self.image_element.width + 4,
            self.image_element.height + 4,
        )

        # Draw selection border
        selection_pen = QPen(QColor(0, 120, 255), 2, Qt.PenStyle.SolidLine)
        painter.setPen(selection_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(rect)

    def _load_image(self) -> None:
        """Load the image from the element data"""
        try:
            self._pixmap = QPixmap()

            if self.image_element.image_data:
                # Load from binary data
                if self._pixmap.loadFromData(self.image_element.image_data):
                    self._logger.debug("Loaded image from binary data")
                else:
                    self._logger.warning("Failed to load image from binary data")
                    self._pixmap = None

            elif self.image_element.image_path:
                # Load from file path
                if self._pixmap.load(self.image_element.image_path):
                    self._logger.debug(
                        "Loaded image from path: %s", self.image_element.image_path
                    )
                else:
                    self._logger.warning(
                        "Failed to load image from path: %s",
                        self.image_element.image_path,
                    )
                    self._pixmap = None
            else:
                self._logger.warning("No image data or path provided")
                self._pixmap = None

            # Create scaled version for better performance if needed
            if self._pixmap and not self._pixmap.isNull():
                self._update_scaled_pixmap()
        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error("Error loading image: %s", e)
            self._pixmap = None

    def _update_scaled_pixmap(self) -> None:
        """Update the scaled pixmap for performance optimization"""
        if not self._pixmap or self._pixmap.isNull():
            return

        target_size = (int(self.image_element.width), int(self.image_element.height))
        pixmap_size = (self._pixmap.width(), self._pixmap.height())

        # Only create scaled version if size is significantly different
        if (
            abs(target_size[0] - pixmap_size[0]) > 10
            or abs(target_size[1] - pixmap_size[1]) > 10
        ):
            self._scaled_pixmap = self._pixmap.scaled(
                target_size[0],
                target_size[1],
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        else:
            self._scaled_pixmap = None

    @override
    def _update_element_position(self, new_position: QPointF) -> None:
        """Update the image element's position when the graphics item moves"""
        if (
            0 <= new_position.x() <= settings.PAGE_WIDTH
            and 0 <= new_position.y() <= settings.PAGE_HEIGHT
        ):
            self.image_element.position = Point(new_position.x(), new_position.y(), 0)

    def set_size(self, width: float, height: float) -> None:
        """Update the image size"""
        self.image_element.width = width
        self.image_element.height = height

        # Update transform origin
        self.setTransformOriginPoint(width / 2, height / 2)

        # Update scaled pixmap
        self._update_scaled_pixmap()
        self.invalidate_cache()

    def set_rotation(self, rotation: float) -> None:
        """Update the image rotation"""
        self.image_element.rotation = rotation
        self.invalidate_cache()
        self.update()

    def reload_image(self) -> None:
        """Reload the image from the element data"""
        self._pixmap = None
        self._scaled_pixmap = None
        self._load_image()
        self.update()

    def get_image_rect(self) -> QRectF:
        """Get the actual image rectangle in scene coordinates"""
        return QRectF(
            self.pos().x(),
            self.pos().y(),
            self.image_element.width,
            self.image_element.height,
        )

    def intersects_point(self, point: QPointF, radius: float = 5.0) -> bool:
        """Check if the image intersects with a point within the given radius"""
        # Convert point to local coordinates
        local_point = self.mapFromScene(point)
        local_rect = QRectF(0, 0, self.image_element.width, self.image_element.height)
        expanded_rect = local_rect.adjusted(-radius, -radius, radius, radius)
        return expanded_rect.contains(local_point)

    def contains_point(self, point: QPointF) -> bool:
        """Check if the point is inside the image"""
        # Convert point to local coordinates and check against local rect
        local_point = self.mapFromScene(point)
        local_rect = QRectF(0, 0, self.image_element.width, self.image_element.height)
        return local_rect.contains(local_point)

    @override
    def type(self) -> int:
        """Return unique type identifier for image items"""
        return hash("ImageGraphicsItem") & 0x7FFFFFFF

    def clone(self) -> "ImageGraphicsItem":
        """Create a copy of this image graphics item"""
        new_image = Image(
            position=Point(
                self.image_element.position.x,
                self.image_element.position.y,
                self.image_element.position.pressure,
            ),
            width=self.image_element.width,
            height=self.image_element.height,
            image_path=self.image_element.image_path,
            image_data=self.image_element.image_data,
            rotation=self.image_element.rotation,
        )
        return ImageGraphicsItem(new_image)

    @override
    def _get_current_size(self) -> tuple[float, float]:
        """Return current image size."""
        return (self.image_element.width, self.image_element.height)

    @override
    def _apply_resize(
        self, new_size: tuple[float, float], new_scene_pos: QPointF
    ) -> None:
        """Apply resize updates for the image element."""
        self.set_size(new_size[0], new_size[1])

        if new_scene_pos != self.pos():
            self.image_element.position = Point(
                new_scene_pos.x(),
                new_scene_pos.y(),
                self.image_element.position.pressure,
            )
            self.setPos(new_scene_pos)

    @override
    def _supports_rotation(self) -> bool:
        return True

    @override
    def _get_rotation(self) -> float:
        return self.image_element.rotation

    @override
    def _set_rotation(self, rotation: float) -> None:
        self.set_rotation(rotation)

    def cleanup(self) -> None:
        """Clean up resources to prevent memory leaks.

        Releases the pixmap memory which can be significant for large images.
        """
        self._pixmap = None
        self._scaled_pixmap = None
