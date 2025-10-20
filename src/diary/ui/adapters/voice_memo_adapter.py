"""Adapter for rendering VoiceMemo elements with QPainter"""

from typing import override
from PyQt6.QtGui import QPainter, QBrush, QColor, QPen, QFont
from PyQt6.QtCore import QRectF, Qt, QPointF

from diary.models.voice_memo import VoiceMemo
from diary.models.page_element import PageElement
from diary.ui.adapters import ElementAdapter


class VoiceMemoAdapter(ElementAdapter):
    """Adapter for rendering VoiceMemo elements"""

    @override
    def can_handle(self, element: PageElement) -> bool:
        """Check if this adapter can handle the given element type"""
        return isinstance(element, VoiceMemo)

    @override
    def render(self, element: PageElement, painter: QPainter) -> None:
        """Render the voice memo using the provided QPainter"""
        if not isinstance(element, VoiceMemo):
            return

        voice_memo = element

        # Create the rectangle where the voice memo will be drawn
        rect = QRectF(
            voice_memo.position.x,
            voice_memo.position.y,
            voice_memo.width,
            voice_memo.height,
        )

        # Save the current painter state
        painter.save()

        # Set rendering hints for smooth appearance
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw the main background circle/rounded rectangle
        painter.setBrush(QBrush(QColor(100, 150, 255, 180)))  # Light blue background
        painter.setPen(QPen(QColor(50, 100, 200), 2))  # Darker blue border
        painter.drawEllipse(rect)

        # Draw microphone icon in the center
        self._draw_microphone_icon(painter, rect)

        # Draw duration text below the icon
        if voice_memo.duration > 0:
            duration_text = self._format_duration(voice_memo.duration)
            painter.setPen(QPen(QColor(0, 0, 0)))
            painter.setFont(QFont("Arial", 8))

            # Position text below the main circle
            text_rect = QRectF(rect.x(), rect.bottom() + 2, rect.width(), 15)
            _ = painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, duration_text)

        # Draw transcript indicator if available
        if voice_memo.transcript:
            painter.setPen(QPen(QColor(0, 150, 0), 2))  # Green indicator
            indicator_rect = QRectF(rect.right() - 8, rect.top(), 6, 6)
            painter.drawEllipse(indicator_rect)

        # Restore the painter state
        painter.restore()

    def _draw_microphone_icon(self, painter: QPainter, rect: QRectF) -> None:
        """Draw a simple microphone icon inside the given rectangle"""
        center = rect.center()
        scale = min(rect.width(), rect.height()) * 0.3

        painter.setPen(QPen(QColor(255, 255, 255), 2))
        painter.setBrush(QBrush(QColor(255, 255, 255)))

        # Draw microphone body (rounded rectangle)
        mic_rect = QRectF(
            center.x() - scale * 0.3, center.y() - scale * 0.8, scale * 0.6, scale * 1.2
        )
        painter.drawRoundedRect(mic_rect, scale * 0.2, scale * 0.2)

        # Draw microphone stand
        painter.drawLine(
            QPointF(center.x(), center.y() + scale * 0.4),
            QPointF(center.x(), center.y() + scale * 0.8),
        )

        # Draw microphone base
        base_width = scale * 0.8
        painter.drawLine(
            QPointF(center.x() - base_width / 2, center.y() + scale * 0.8),
            QPointF(center.x() + base_width / 2, center.y() + scale * 0.8),
        )

    def _format_duration(self, duration: float) -> str:
        """Format duration in seconds to a readable string"""
        if duration < 60:
            return f"{duration:.0f}s"
        elif duration < 3600:
            minutes = int(duration // 60)
            seconds = int(duration % 60)
            return f"{minutes}:{seconds:02d}"
        else:
            hours = int(duration // 3600)
            minutes = int((duration % 3600) // 60)
            seconds = int(duration % 60)
            return f"{hours}:{minutes:02d}:{seconds:02d}"
