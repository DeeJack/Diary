"""Graphics item for rendering text elements using QGraphicsItem"""

from typing import cast, override

from PyQt6.QtCore import QPointF, QRect, QRectF, Qt
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
    QGraphicsTextItem,
    QStyleOptionGraphicsItem,
    QWidget,
)

from diary.config import settings
from diary.models.elements.text import Text
from diary.models.point import Point

from .resizable_graphics_item import ResizableGraphicsItem


class TextGraphicsItem(ResizableGraphicsItem):
    """Graphics item for rendering text elements"""

    _HINT_TEXT = "Type here"

    def __init__(self, text_element: Text, parent: QGraphicsItem | None = None):
        super().__init__(text_element, parent)
        self._font: QFont | None = None
        self._font_metrics: QFontMetrics | None = None
        self._text_rect: QRectF | None = None
        self._show_cursor: bool = False
        self._edit_item: QGraphicsTextItem | None = None
        self._resize_start_font_size: float | None = None

        # Configure item flags for text
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)

        self.setPos(text_element.position.x, text_element.position.y)

        text_rect = self._text_positioned_box(self._get_display_text())
        # Enable transformations (use local coordinates)
        self.setTransformOriginPoint(
            (settings.PAGE_WIDTH - text_element.position.x) / 2, text_rect.height() / 2
        )

    @property
    def text_element(self) -> Text:
        """Get the text element"""
        return cast(Text, self._element)

    @override
    def _calculate_bounding_rect(self) -> QRectF:
        """Calculate the bounding rectangle for the text"""
        display_text = self._get_display_text()
        positioned_rect = self._text_positioned_box(display_text)

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
        # If editing, skip custom painting
        if self._edit_item is not None:
            if painter:
                self.configure_painter_quality(painter)
                if self.isSelected():
                    self._draw_selection_highlight(painter)
                    self._draw_resize_handles(painter)
                if not self.text_element.text:
                    self._draw_hint_text(painter)
            return

        if not painter:
            return

        # Configure painter for high-quality text rendering
        self.configure_painter_quality(painter)

        # Draw selection highlight if selected
        if self.isSelected():
            self._draw_selection_highlight(painter)
            self._draw_resize_handles(painter)

        # Set up font and color
        font = self._get_font()
        painter.setFont(font)

        if not self.text_element.text:
            self._draw_hint_text(painter)
            return

        text_color = QColor(self.text_element.color)
        painter.setPen(QPen(text_color))

        # Draw the text at the element's position
        text_rect = self._text_positioned_box()
        painter.drawText(
            text_rect,
            Qt.TextFlag.TextWordWrap,
            self.text_element.text,
        )

        # Draw cursor if this text is being edited (optional future enhancement)
        if hasattr(self, "_show_cursor") and self._show_cursor:
            self._draw_text_cursor(painter)

    def _draw_selection_highlight(self, painter: QPainter) -> None:
        """Draw selection highlight behind the text"""
        # Get text bounds without padding
        positioned_rect = self._text_positioned_box(self._get_display_text())

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

        return self._font

    @override
    def _update_element_position(self, new_position: QPointF) -> None:
        """Update the text element's position when the graphics item moves"""
        if (
            0 <= new_position.x() <= settings.PAGE_WIDTH
            and 0 <= new_position.y() <= settings.PAGE_HEIGHT
        ):
            self.text_element.position = Point(new_position.x(), new_position.y(), 0)
            self.invalidate_cache()

    @override
    def _resize_rect(self) -> QRectF:
        """Return the text bounds used for resizing handles."""
        return self._text_positioned_box(self._get_display_text())

    @override
    def _get_current_size(self) -> tuple[float, float]:
        """Return the current text bounds size."""
        text_rect = self._text_positioned_box(self._get_display_text())
        return (text_rect.width(), text_rect.height())

    @override
    def _resize_min_size(self) -> float:
        """Minimum size for text resizing."""
        return 8.0

    @override
    def mousePressEvent(self, event: QGraphicsSceneMouseEvent | None) -> None:
        """Handle mouse press events for text editing."""
        if event and event.button() == Qt.MouseButton.LeftButton:
            handle = self._get_handle_at_point(event.pos())
            if handle:
                self._resize_start_font_size = self.text_element.size_px
        super().mousePressEvent(event)

    @override
    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent | None) -> None:
        """Handle mouse release events."""
        if self._resize_start_font_size is not None:
            self._resize_start_font_size = None
        super().mouseReleaseEvent(event)

    @override
    def _apply_resize(
        self, new_size: tuple[float, float], new_scene_pos: QPointF
    ) -> None:
        """Resize text by adjusting font size and position."""
        start_rect = self._resize_start_rect or self._text_positioned_box(
            self._get_display_text()
        )
        start_font_size = self._resize_start_font_size or self.text_element.size_px

        if start_rect.width() > 0 and start_rect.height() > 0:
            width_scale = new_size[0] / start_rect.width()
            height_scale = new_size[1] / start_rect.height()
            scale = max(width_scale, height_scale)
        else:
            scale = 1.0

        new_font_size = max(6.0, start_font_size * scale)
        self.set_font_size(new_font_size)

        if new_scene_pos != self.pos():
            self.text_element.position = Point(
                new_scene_pos.x(),
                new_scene_pos.y(),
                self.text_element.position.pressure,
            )
            self.setPos(new_scene_pos)

        text_rect = self._text_positioned_box(self._get_display_text())
        self.setTransformOriginPoint(
            (settings.PAGE_WIDTH - self.text_element.position.x) / 2,
            text_rect.height() / 2,
        )

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
        return self._text_positioned_box(self._get_display_text())

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
        """Start text editing mode"""
        if self._edit_item is not None:
            return

        # Create a QGraphicsTextItem for editing
        self._edit_item = QGraphicsTextItem(self.text_element.text, self)
        font = self._get_font()
        self._edit_item.setFont(font)
        self._edit_item.setDefaultTextColor(QColor(self.text_element.color))
        self._edit_item.setPos(
            0,
            -QFontMetrics(font).ascent(),
        )

        # Set width constraint for word wrap
        self._edit_item.setTextWidth(settings.PAGE_WIDTH - self.text_element.position.x)
        self._edit_item.setToolTip("Edit text here")

        # Make it editable and focusable
        self._edit_item.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextEditorInteraction
        )

        # Connect to text changes
        if document := self._edit_item.document():
            document.contentsChanged.connect(self._on_text_changed)

        self._edit_item.setFocus()

        # Hide the painted text
        self._show_cursor = False
        self.update()
        self.invalidate_cache()
        self._edit_item.setFocus()

    def stop_editing(self) -> None:
        """Stop text editing mode"""
        if self._edit_item is None:
            return

        # Get the final text
        final_text = self._edit_item.toPlainText()
        self.set_text(final_text)

        # Clean up the edit item
        if scene := self.scene():
            scene.removeItem(self._edit_item)
        self._edit_item.deleteLater()
        self._edit_item = None

        self._show_cursor = False
        self.update()

    @override
    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent | None) -> None:
        """Handle double-click events for text editing"""
        if event and event.button() == Qt.MouseButton.LeftButton:
            self.start_editing()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def _on_text_changed(self) -> None:
        """Handle live text changes during editing"""
        if self._edit_item:
            # Update the underlying text element in real-time
            new_text = self._edit_item.toPlainText()
            self.text_element.text = new_text
            self.invalidate_cache()

    @override
    def _handle_selection_change(self, _: bool) -> None:
        selected = _
        if self._edit_item is not None and not selected:
            self.stop_editing()

        return super()._handle_selection_change(_)

    def _text_positioned_box(self, text: str | None = None) -> QRectF:
        font = self._get_font()
        font_metrics = QFontMetrics(font)
        display_text = text if text is not None else self.text_element.text

        text_bound_rect = QRect(
            0,
            0,
            int(settings.PAGE_WIDTH - self.text_element.position.x),
            int(settings.PAGE_HEIGHT - self.text_element.position.y),
        )
        # Get text dimensions
        text_rect = font_metrics.boundingRect(
            text_bound_rect, Qt.TextFlag.TextWordWrap, display_text
        )
        positioned_rect = QRectF(
            0,
            -font_metrics.ascent(),
            text_rect.width(),
            text_rect.height(),
        )
        return positioned_rect

    def _get_display_text(self) -> str:
        return self.text_element.text or self._HINT_TEXT

    def _draw_hint_text(self, painter: QPainter) -> None:
        font = self._get_font()
        hint_font = QFont(font)
        hint_font.setItalic(True)
        painter.setFont(hint_font)

        hint_color = QColor(self.text_element.color)
        hint_color.setAlpha(120)
        painter.setPen(QPen(hint_color))

        text_rect = self._text_positioned_box(self._HINT_TEXT)
        painter.drawText(
            text_rect,
            Qt.TextFlag.TextWordWrap,
            self._HINT_TEXT,
        )
