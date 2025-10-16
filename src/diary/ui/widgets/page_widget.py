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
    def __init__(self, page: Page = Page()):
        super().__init__()
        self.page_width: int = settings.PAGE_WIDTH
        self.page_height: int = settings.PAGE_HEIGHT

        self.setFixedSize(self.page_width, self.page_height)
        self.setMinimumWidth(self.page_width)

        self.current_stroke: Stroke | None = None
        self.page: Page = page

        self.is_drawing: bool = False
        self.base_thickness: float = 0.5

    @override
    def paintEvent(self, a0: QPaintEvent | None) -> None:
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(0xE0, 0xE0, 0xE0))

        self.draw_horizontal_lines(painter)

        self.draw_previous_strokes(painter)
        self.draw_current_strokes(painter)

        return super().paintEvent(a0)

    def draw_horizontal_lines(self, painter: QPainter):
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

    def draw_previous_strokes(self, painter: QPainter):
        for stroke in self.page.strokes:
            self.draw_stroke(stroke, painter)

    def draw_stroke(self, stroke: Stroke, painter: QPainter):
        if len(stroke.points) < 1:
            return
        first_point = stroke.points[0]
        pen = QPen(QColor(stroke.color), first_point.pressure)
        painter.setPen(pen)

        if len(stroke.points) == 1:
            painter.drawPoint(QPointF(first_point.x, first_point.y))
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        for i in range(len(stroke.points) - 1):
            p1 = stroke.points[i]
            p2 = stroke.points[i + 1]
            avg_pressure = (p1.pressure + p2.pressure) / 2
            width = avg_pressure * self.base_thickness * 2

            path: QPainterPath = QPainterPath()
            path.moveTo(p1.x, p2.y)

            if i < len(stroke.points) - 2:
                p3 = stroke.points[i + 2]
                mid_x = (p2.x + p3.x) / 2
                mid_y = (p2.y + p3.y) / 2
                path.quadTo(p2.x, p2.y, mid_x, mid_y)
            else:
                path.lineTo(p2.x, p2.y)

            pen = QPen(QColor(stroke.color), width)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.drawPath(path)

    def draw_current_strokes(self, painter: QPainter):
        if self.current_stroke is not None:
            self.draw_stroke(self.current_stroke, painter)

    def continue_drawing(self, event: QTabletEvent, pos: QPoint):
        if self.current_stroke is None:
            self.current_stroke = Stroke()
        pressure = event.pressure()
        self.current_stroke.points.append(Point(pos.x(), pos.y(), pressure))
        self.update()

    def stop_drawing(self):
        print("Stopping drawing")
        self.is_drawing = False
        if self.current_stroke is None:
            return
        self.page.strokes.append(self.current_stroke)
        self.current_stroke = None
        self.update()

    def handle_tablet_event(self, event: QTabletEvent, pos: QPoint):
        """This should now receive events!"""
        if event.type() == QTabletEvent.Type.TabletPress:
            self.is_drawing = True
            self.current_stroke = Stroke()
        elif event.type() == QTabletEvent.Type.TabletMove:
            if self.is_drawing:
                self.continue_drawing(event, pos)
        elif event.type() == QTabletEvent.Type.TabletRelease:
            self.stop_drawing()
        event.accept()
