"""Adapter for rendering Image elements with QPainter"""

import logging
from typing import override

from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QPainter, QPen, QPixmap

from diary.models import Image, PageElement
from diary.ui.adapters import ElementAdapter


class ImageAdapter(ElementAdapter):
    """Adapter for rendering Image elements"""

    @override
    def can_handle(self, element: PageElement) -> bool:
        """Check if this adapter can handle the given element type"""
        return isinstance(element, Image)

    @override
    def render(self, element: PageElement, painter: QPainter) -> None:
        """Render the image using the provided QPainter"""
        if not isinstance(element, Image):
            return

        image = element
        logging.getLogger("ImageAdapter").debug(
            "Rendering image: %s, with path: %s and data: %s...%s",
            image,
            image.image_path,
            image.image_data[:10] if image.image_data else None,
            image.image_data[-10:] if image.image_data else None,
        )
        # Create the rectangle where the image will be drawn
        rect = QRectF(image.position.x, image.position.y, image.width, image.height)
        # Save the current painter state
        painter.save()
        # Apply rotation if needed
        if image.rotation != 0.0:
            center = rect.center()
            painter.translate(center)
            painter.rotate(image.rotation)
            painter.translate(-center)
        # Try to load and draw the actual image
        pixmap = None
        if image.image_path:
            pixmap = QPixmap(image.image_path)
        elif image.image_data:
            pixmap = QPixmap()
            _ = pixmap.loadFromData(image.image_data)

        if pixmap and not pixmap.isNull():
            # Draw the actual image
            painter.drawPixmap(rect, pixmap, pixmap.rect().toRectF())
        else:
            # Draw a placeholder rectangle if image can't be loaded
            painter.setBrush(QBrush(QColor(200, 200, 200, 128)))
            painter.setPen(QPen(QColor(100, 100, 100), 2, Qt.PenStyle.DashLine))
            painter.drawRect(rect)

            # Draw an "X" to indicate missing image
            painter.setPen(QPen(QColor(150, 150, 150), 1))
            painter.drawLine(rect.topLeft(), rect.bottomRight())
            painter.drawLine(rect.topRight(), rect.bottomLeft())

            # Draw "IMG" text in the center
            painter.setPen(QPen(QColor(100, 100, 100)))
            _ = painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "IMG")

        # Restore the painter state
        painter.restore()

    @override
    def rect(self, element: PageElement) -> QRectF:
        if not isinstance(element, Image):
            return QRectF()
        return QRectF(
            element.position.x,
            element.position.y,
            element.position.x + element.width,
            element.position.y + element.height,
        )

    @staticmethod
    def read_image(file_path: str) -> tuple[bytes, int, int]:
        """Reads the image from a path, and returns bytes, height, width"""
        pixmap = QPixmap(file_path)
        if pixmap.isNull():
            raise ValueError("Couldn't load image")

        MAX_DIMENSION = 1024.0
        if pixmap.width() > MAX_DIMENSION or pixmap.height() > MAX_DIMENSION:
            logging.getLogger("ImageAdapter").debug(
                "Scaled: %s %s", pixmap.width(), pixmap.height()
            )
            # Scale the pixmap down, keeping aspect ratio
            pixmap = pixmap.scaled(
                int(MAX_DIMENSION),
                int(MAX_DIMENSION),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

        # Compress to JPG, quality 80
        byte_array = QByteArray()
        buffer = QBuffer(byte_array)
        _ = buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        # Save the pixmap to the buffer in JPEG format, quality 80
        _ = pixmap.save(buffer, "JPG", 80)

        image_bytes = byte_array.data()
        return (image_bytes, pixmap.height(), pixmap.width())
