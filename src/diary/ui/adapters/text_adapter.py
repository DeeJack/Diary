"""Adapter for rendering Text elements with QPainter"""

from typing import override

from PyQt6.QtCore import QPointF, QRectF
from PyQt6.QtGui import QFont, QFontMetrics, QPainter

from diary.models import PageElement, Text
from diary.ui.adapters import ElementAdapter


class TextAdapter(ElementAdapter):
    """Adapter for rendering Text elements"""

    @override
    def can_handle(self, element: PageElement) -> bool:
        """Check if this adapter can handle the given element type"""
        return isinstance(element, Text)

    @override
    def render(self, element: PageElement, painter: QPainter) -> None:
        """Render the image using the provided QPainter"""
        if not isinstance(element, Text):
            return

        painter.save()
        painter.setFont(QFont("Times New Roman", pointSize=int(element.size_px)))
        painter.drawText(QPointF(element.position.x, element.position.y), element.text)
        painter.restore()

    @override
    def rect(self, element: PageElement) -> QRectF:
        if not isinstance(element, Text):
            return QRectF()

        font = QFont("Times New Roman", pointSize=int(element.size_px))

        font_metrics = QFontMetrics(font)
        text_rect = font_metrics.boundingRect(element.text)

        return QRectF(
            element.position.x,
            element.position.y,
            text_rect.width(),
            text_rect.height(),
        )
