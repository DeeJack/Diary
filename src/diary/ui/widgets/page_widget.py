from typing import override
from PyQt6.QtWidgets import QWidget
from PyQt6 import QtGui
from PyQt6.QtGui import (
    QPainter,
    QColor,
    QPaintEvent,
    QBrush,
    QPainterPath,
    QPen,
    QTabletEvent,
)
from PyQt6.QtCore import QPoint, QPointF, Qt

from diary.models.page import Page
from diary.config import settings
from diary.models.point import Point
from diary.models.stroke import Stroke


class PageWidget(QWidget):
    """Represents the UI of a Page in the Notebook"""

    def __init__(self, page: Page | None):
        super().__init__()
        self.page_width: int = settings.PAGE_WIDTH
        self.page_height: int = settings.PAGE_HEIGHT
        self.current_stroke: Stroke | None = None
        self.page: Page = page or Page()
        self.is_drawing: bool = False
        self.base_thickness: float = 0.5

        self.setFixedSize(self.page_width, self.page_height)
        self.setMinimumWidth(self.page_width)

    @override
    def paintEvent(self, a0: QPaintEvent | None) -> None:
        """Renders the current page"""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.fillRect(self.rect(), QColor(0xE0, 0xE0, 0xE0))

        self.draw_horizontal_lines(painter)
        self.draw_previous_strokes(painter)
        self.draw_current_stroke(painter)
        return super().paintEvent(a0)

    def draw_horizontal_lines(self, painter: QPainter):
        """Draws the usual horizontal lines on a notebook page"""
        for line in range(0, self.page_height, settings.PAGE_LINES_SPACING):
            painter.setBrush(QBrush(QColor(0xDD, 0xCD, 0xC4)))
            painter.setPen(QColor(0xDD, 0xCD, 0xC4))
            painter.setOpacity(0.9)

            painter.drawLine(
                settings.PAGE_LINES_MARING,
                line,
                self.page_width - settings.PAGE_LINES_MARING,
                line,
            )

    def draw_stroke(self, stroke: Stroke, painter: QPainter):
        """Draw a stroke on the painter"""
        if len(stroke.points) < 1:
            return
        # painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if len(stroke.points) == 1:
            first_point = stroke.points[0]
            width = max(1, first_point.pressure * self.base_thickness * 2)
            pen = QPen(QColor(stroke.color), width)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawPoint(QPointF(first_point.x, first_point.y))
            return
        path = QPainterPath()
        first_point = stroke.points[0]
        path.moveTo(first_point.x, first_point.y)

        # Draw lines to all subsequent points
        for i in range(1, len(stroke.points)):
            point = stroke.points[i]
            path.lineTo(point.x, point.y)

        # Draw the path with variable width based on average pressure
        total_pressure = sum(point.pressure for point in stroke.points)
        avg_pressure = total_pressure / len(stroke.points)
        width = max(1, avg_pressure * self.base_thickness * 2)

        pen = QPen(QColor(stroke.color), width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawPath(path)

    def draw_current_stroke(self, painter: QPainter):
        """Draw the current stroke on the page"""
        if self.current_stroke is not None:
            self.draw_stroke(self.current_stroke, painter)

    def draw_previous_strokes(self, painter: QPainter):
        """Draw the strokes that have already been saved"""
        for stroke in self.page.strokes:
            self.draw_stroke(stroke, painter)

    def continue_drawing(self, event: QTabletEvent, pos: QPoint):
        """Continues current stroke"""
        if self.current_stroke is None:
            self.current_stroke = Stroke()
        pressure = event.pressure()
        self.current_stroke.points.append(Point(pos.x(), pos.y(), pressure))
        self.update()

    def stop_drawing(self):
        """Stops current stroke"""
        self.is_drawing = False
        if self.current_stroke is None:
            return
        self.page.strokes.append(self.current_stroke)
        self.current_stroke = None
        self.update()

    def handle_tablet_event(self, event: QTabletEvent, pos: QPoint):
        """Handles Pen events, forwarded by the Notebook"""
        if event.type() == QTabletEvent.Type.TabletPress:
            self.is_drawing = True
            self.current_stroke = Stroke()
        elif event.type() == QTabletEvent.Type.TabletMove:
            if self.is_drawing:
                self.continue_drawing(event, pos)
        elif event.type() == QTabletEvent.Type.TabletRelease:
            self.stop_drawing()
        event.accept()
