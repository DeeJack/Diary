"""Graphics item for rendering text elements using QGraphicsItem"""

from typing import cast, override

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QPainter,
    QPen,
)
from PyQt6.QtWidgets import (
    QGraphicsItem,
    QGraphicsSceneMouseEvent,
    QStyleOptionGraphicsItem,
    QWidget,
)

from diary.models.elements.text import Text
from diary.models.point import Point

from .base_graphics_item import BaseGraphicsItem


class TextGraphicsItem(BaseGraphicsItem):
    """Graphics item for rendering text elements"""

    def __init__(self, text_element: Text, parent: QGraphicsItem | None = None):
        super().__init__(text_element, parent)
        self._font: QFont | None = None
        self._font_metrics: QFontMetrics | None = None
        self._text_rect: QRectF | None = None
        self._show_cursor: bool = False

        # Configure item flags for text
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)

    @property
    def text_element(self) -> Text:
        """Get the text element"""
        return cast(Text, self._element)

    @override
    def _calculate_bounding_rect(self) -> QRectF:
        """Calculate the bounding rectangle for the text"""
        if not self.text_element.text:
            return QRectF(
                self.text_element.position.x, self.text_element.position.y, 10, 10
            )

        font = self._get_font()
        font_metrics = QFontMetrics(font)

        # Get text dimensions
        text_rect = font_metrics.boundingRect(self.text_element.text)

        # Position the rectangle at the text element's position
        positioned_rect = QRectF(
            self.text_element.position.x,
            self.text_element.position.y - font_metrics.ascent(),
            text_rect.width(),
            text_rect.height(),
        )

        # Add some padding for selection highlighting
        padding = 4.0
        return positioned_rect.adjusted(-padding, -padding, padding, padding)

    @override
    def paint(
        self,
        painter: QPainter | None,
        option: QStyleOptionGraphicsItem | None,
        widget: QWidget | None = None,
    ) -> None:
        """Paint the text with high-quality font rendering"""
        if not self.text_element.text or not painter:
            return

        # Configure painter for high-quality text rendering
        self.configure_painter_quality(painter)

        # Draw selection highlight if selected
        if self.isSelected():
            self._draw_selection_highlight(painter)

        # Set up font and color
        font = self._get_font()
        painter.setFont(font)

        text_color = QColor(self.text_element.color)
        painter.setPen(QPen(text_color))

        # Draw the text at the element's position
        text_point = QPointF(self.text_element.position.x, self.text_element.position.y)
        painter.drawText(text_point, self.text_element.text)

        # Draw cursor if this text is being edited (optional future enhancement)
        if hasattr(self, "_show_cursor") and self._show_cursor:
            self._draw_text_cursor(painter)

    def _draw_selection_highlight(self, painter: QPainter) -> None:
        """Draw selection highlight behind the text"""
        # Get text bounds without padding
        font = self._get_font()
        font_metrics = QFontMetrics(font)
        text_rect = font_metrics.boundingRect(self.text_element.text)

        positioned_rect = QRectF(
            self.text_element.position.x,
            self.text_element.position.y - font_metrics.ascent(),
            text_rect.width(),
            text_rect.height(),
        )

        # Draw semi-transparent selection background
        selection_color = QColor(0, 120, 255, 64)  # Semi-transparent blue
        painter.fillRect(positioned_rect, selection_color)

        # Draw selection border
        border_pen = QPen(QColor(0, 120, 255, 128))
        border_pen.setWidth(2)
        painter.setPen(border_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(positioned_rect)

    def _draw_text_cursor(self, painter: QPainter) -> None:
        """Draw a text editing cursor (for future text editing enhancement)"""
        cursor_pen = QPen(QColor(0, 0, 0))
        cursor_pen.setWidth(2)
        painter.setPen(cursor_pen)

        # Calculate cursor position (at end of text for now)
        font_metrics = QFontMetrics(self._get_font())
        text_width = font_metrics.horizontalAdvance(self.text_element.text)

        cursor_x = self.text_element.position.x + text_width
        cursor_y1 = self.text_element.position.y - font_metrics.ascent()
        cursor_y2 = self.text_element.position.y + font_metrics.descent()

        painter.drawLine(QPointF(cursor_x, cursor_y1), QPointF(cursor_x, cursor_y2))

    def _get_font(self) -> QFont:
        """Get or create the font for this text element"""
        if self._font is None:
            self._font = QFont()
            self._font.setPointSizeF(self.text_element.size_px)
            # You can add more font properties here (family, weight, style, etc.)

        return self._font

    @override
    def _update_element_position(self, new_position: QPointF) -> None:
        """Update the text element's position when the graphics item moves"""
        self.text_element.position = Point(
            new_position.x(), new_position.y(), self.text_element.position.pressure
        )
        self.invalidate_cache()
        self.update()

    def set_text(self, text: str) -> None:
        """Update the text content"""
        self.text_element.text = text
        self._font_metrics = None  # Invalidate metrics cache
        self.invalidate_cache()

    def set_font_size(self, size: float) -> None:
        """Update the font size"""
        self.text_element.size_px = size
        self._font = None  # Invalidate font cache
        self._font_metrics = None  # Invalidate metrics cache
        self.invalidate_cache()

    def set_color(self, color: str) -> None:
        """Update the text color"""
        self.text_element.color = color
        self.update()

    def get_text_rect(self) -> QRectF:
        """Get the actual text rectangle (without padding)"""
        if not self.text_element.text:
            return QRectF()

        font = self._get_font()
        font_metrics = QFontMetrics(font)
        text_rect = font_metrics.boundingRect(self.text_element.text)

        return QRectF(
            self.text_element.position.x,
            self.text_element.position.y - font_metrics.ascent(),
            text_rect.width(),
            text_rect.height(),
        )

    def intersects_point(self, point: QPointF, radius: float = 5.0) -> bool:
        """Check if the text intersects with a point within the given radius"""
        text_rect = self.get_text_rect()
        expanded_rect = text_rect.adjusted(-radius, -radius, radius, radius)
        return expanded_rect.contains(point)

    @override
    def type(self) -> int:
        """Return unique type identifier for text items"""
        return hash("TextGraphicsItem") & 0x7FFFFFFF

    def clone(self) -> "TextGraphicsItem":
        """Create a copy of this text graphics item"""
        new_text = Text(
            text=self.text_element.text,
            position=Point(
                self.text_element.position.x,
                self.text_element.position.y,
                self.text_element.position.pressure,
            ),
            color=self.text_element.color,
            size_px=self.text_element.size_px,
        )
        return TextGraphicsItem(new_text)

    def start_editing(self) -> None:
        """Start text editing mode (future enhancement)"""
        self._show_cursor = True
        self.update()

    def stop_editing(self) -> None:
        """Stop text editing mode (future enhancement)"""
        self._show_cursor = False
        self.update()

    @override
    def mousePressEvent(self, event: QGraphicsSceneMouseEvent | None) -> None:
        """Handle mouse press events for text editing"""
        if event and event.button() == Qt.MouseButton.LeftButton:
            pass
        super().mousePressEvent(event)

    @override
    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent | None) -> None:
        """Handle double-click events for text editing"""
        if event and event.button() == Qt.MouseButton.LeftButton:
            pass
        super().mouseDoubleClickEvent(event)
