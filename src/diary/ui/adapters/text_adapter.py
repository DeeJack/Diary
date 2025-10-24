"""Adapter for rendering Text elements with QPainter"""

from typing import override
from PyQt6.QtGui import QFont, QPainter
from PyQt6.QtCore import QPointF

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
