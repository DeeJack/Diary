"""Graphics item for rendering image elements using QGraphicsItem architecture"""

import logging
from typing import cast, override

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QColor,
    QPainter,
    QPen,
    QPixmap,
    QTransform,
)
from PyQt6.QtWidgets import (
    QGraphicsItem,
    QGraphicsSceneMouseEvent,
    QStyleOptionGraphicsItem,
    QWidget,
)

from diary.models.elements.image import Image
from diary.models.point import Point

from .base_graphics_item import BaseGraphicsItem


class ImageGraphicsItem(BaseGraphicsItem):
    """Graphics item for rendering image elements with support for rotation and scaling"""

    def __init__(self, image_element: Image, parent: QGraphicsItem | None = None):
        super().__init__(image_element, parent)
        self._pixmap: QPixmap | None = None
        self._scaled_pixmap: QPixmap | None = None
        self._current_scale: float = 1.0
        self._logger: logging.Logger = logging.getLogger("ImageGraphicsItem")
        self._resize_handle: str
        self._resize_start_pos: QPointF
        self._resize_start_rect: QRectF

        # Configure item flags for images
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)

        # Enable transformations
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
        # Base rectangle from image dimensions
        rect = QRectF(
            self.image_element.position.x,
            self.image_element.position.y,
            self.image_element.width,
            self.image_element.height,
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
            self._draw_selection_highlight(painter)

        # Save painter state for transformations
        painter.save()

        # Apply rotation if specified
        if self.image_element.rotation != 0.0:
            center_x = self.image_element.position.x + self.image_element.width / 2
            center_y = self.image_element.position.y + self.image_element.height / 2

            painter.translate(center_x, center_y)
            painter.rotate(self.image_element.rotation)
            painter.translate(-center_x, -center_y)

        # Draw the image
        target_rect = QRectF(
            self.image_element.position.x,
            self.image_element.position.y,
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
            self._draw_resize_handles(painter)

    def _draw_placeholder(self, painter: QPainter) -> None:
        """Draw a placeholder when image cannot be loaded"""
        rect = QRectF(
            self.image_element.position.x,
            self.image_element.position.y,
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
            self.image_element.position.x - 2,
            self.image_element.position.y - 2,
            self.image_element.width + 4,
            self.image_element.height + 4,
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

        # Calculate handle positions
        left = self.image_element.position.x
        top = self.image_element.position.y
        right = left + self.image_element.width
        bottom = top + self.image_element.height

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
                        f"Loaded image from path: {self.image_element.image_path}"
                    )
                else:
                    self._logger.warning(
                        f"Failed to load image from path: {self.image_element.image_path}"
                    )
                    self._pixmap = None

            else:
                self._logger.warning("No image data or path provided")
                self._pixmap = None

            # Create scaled version for better performance if needed
            if self._pixmap and not self._pixmap.isNull():
                self._update_scaled_pixmap()

        except Exception as e:
            self._logger.error(f"Error loading image: {e}")
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
        self.image_element.position = Point(
            new_position.x(), new_position.y(), self.image_element.position.pressure
        )

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
        self.update()

    def reload_image(self) -> None:
        """Reload the image from the element data"""
        self._pixmap = None
        self._scaled_pixmap = None
        self._load_image()
        self.update()

    def get_image_rect(self) -> QRectF:
        """Get the actual image rectangle (without padding)"""
        return QRectF(
            self.image_element.position.x,
            self.image_element.position.y,
            self.image_element.width,
            self.image_element.height,
        )

    def intersects_point(self, point: QPointF, radius: float = 5.0) -> bool:
        """Check if the image intersects with a point within the given radius"""
        image_rect = self.get_image_rect()
        expanded_rect = image_rect.adjusted(-radius, -radius, radius, radius)
        return expanded_rect.contains(point)

    def contains_point(self, point: QPointF) -> bool:
        """Check if the point is inside the image"""
        # Handle rotation by transforming the point
        if self.image_element.rotation != 0.0:
            center_x = self.image_element.position.x + self.image_element.width / 2
            center_y = self.image_element.position.y + self.image_element.height / 2

            # Create inverse rotation transform
            transform = (
                QTransform()
                .translate(center_x, center_y)
                .rotate(-self.image_element.rotation)
                .translate(-center_x, -center_y)
            )

            # Transform the point
            transformed_point = transform.map(point)
            return self.get_image_rect().contains(transformed_point)
        else:
            return self.get_image_rect().contains(point)

    def get_handle_at_point(self, point: QPointF) -> str | None:
        """Get the resize handle at the given point, if any"""
        if not self.isSelected():
            return None

        handle_size = 8.0
        left = self.image_element.position.x
        top = self.image_element.position.y
        right = left + self.image_element.width
        bottom = top + self.image_element.height

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
                self._resize_start_rect = self.get_image_rect()
                event.accept()
                return

        super().mousePressEvent(event)

    @override
    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent | None) -> None:
        """Handle mouse move events for resizing"""
        if not event:
            return
        if hasattr(self, "_resize_handle") and self._resize_handle:
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
        """Handle image resizing based on handle movement"""
        if not hasattr(self, "_resize_handle") or not hasattr(
            self, "_resize_start_rect"
        ):
            return

        start_rect = self._resize_start_rect
        handle = self._resize_handle

        # Calculate new dimensions based on handle
        if handle == "bottom-right":
            new_width = max(20, current_pos.x() - start_rect.left())
            new_height = max(20, current_pos.y() - start_rect.top())
            self.set_size(new_width, new_height)

        elif handle == "top-left":
            new_width = max(20, start_rect.right() - current_pos.x())
            new_height = max(20, start_rect.bottom() - current_pos.y())

            # Update position and size
            self.image_element.position = Point(
                current_pos.x(), current_pos.y(), self.image_element.position.pressure
            )
            self.set_size(new_width, new_height)

        # Add more handle cases as needed

        self.invalidate_cache()
