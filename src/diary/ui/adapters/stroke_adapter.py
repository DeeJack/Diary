"""Adapter for rendering Stroke elements with QPainter"""

from typing import override
from PyQt6.QtGui import QPainter, QPen, QColor, QPainterPath
from PyQt6.QtCore import QPointF, Qt

from diary.models.stroke import Stroke
from diary.models.page_element import PageElement
from diary.ui.adapters import ElementAdapter


class StrokeAdapter(ElementAdapter):
    """Adapter for rendering Stroke elements"""

    def __init__(self, base_thickness: float = 3.0):
        self.base_thickness: float = base_thickness

    @override
    def can_handle(self, element: PageElement) -> bool:
        """Check if this adapter can handle the given element type"""
        return isinstance(element, Stroke)

    @override
    def render(self, element: PageElement, painter: QPainter) -> None:
        """Render the stroke using the provided QPainter"""
        if not isinstance(element, Stroke):
            return

        stroke = element
        if len(stroke.points) < 1:
            return

        if len(stroke.points) == 1:
            first_point = stroke.points[0]
            width = self._calculate_width_from_pressure(first_point.pressure)
            pen = QPen(QColor(stroke.color), width)
            # pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawPoint(QPointF(first_point.x, first_point.y))
            return

        for i in range(len(stroke.points) - 1):
            p1 = stroke.points[i]
            p2 = stroke.points[i + 1]
            avg_pressure = (p1.pressure + p2.pressure) / 2
            width = self._calculate_width_from_pressure(avg_pressure)

            path = QPainterPath()
            path.moveTo(p1.x, p1.y)

            if i < len(stroke.points) - 2:
                p3 = stroke.points[i + 2]
                mid_x = (p2.x + p3.x) / 2
                mid_y = (p2.y + p3.y) / 2
                path.quadTo(p2.x, p2.y, mid_x, mid_y)
            else:
                path.lineTo(p2.x, p2.y)

            pen = QPen(QColor(stroke.color), width)
            # pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            # pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.drawPath(path)

    def _calculate_width_from_pressure(self, pressure: float) -> float:
        """Calculate stroke width based on pressure"""
        # Pressure ranges from 0.0 to 1.0
        min_width = 1.0
        max_width = self.base_thickness * 2
        return min_width + (pressure * (max_width - min_width))
