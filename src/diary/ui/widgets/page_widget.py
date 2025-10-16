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
    QPixmap,
    QResizeEvent,
    QTabletEvent,
)
from PyQt6.QtCore import QPoint, QPointF, QRect, Qt

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
        self.needs_full_redraw: bool = True
        self.backing_pixmap: QPixmap | None = None

        self.setFixedSize(self.page_width, self.page_height)
        self.setMinimumWidth(self.page_width)

    def ensure_backing_pixmap(self):
        """Init backing pixmap"""
        if self.backing_pixmap is None or self.backing_pixmap.size() != self.size():
            self.backing_pixmap = QPixmap(self.size())
            self.needs_full_redraw = True

    def render_backing_pixmap(self):
        """Renders the pixmap"""
        if not self.backing_pixmap:
            return

        painter = QPainter(self.backing_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.backing_pixmap.rect(), QColor(0xE0, 0xE0, 0xE0))
        self.draw_horizontal_lines(painter)
        self.draw_previous_strokes(painter)
        _ = painter.end()
        self.needs_full_redraw = False

    @override
    def paintEvent(self, a0: QPaintEvent | None) -> None:
        """Renders the current page"""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.ensure_backing_pixmap()

        if self.needs_full_redraw:
            self.render_backing_pixmap()

        if self.backing_pixmap:
            painter.drawPixmap(0, 0, self.backing_pixmap)
        # painter.fillRect(self.rect(), QColor(0xE0, 0xE0, 0xE0))
        # self.draw_horizontal_lines(painter)
        # self.draw_previous_strokes(painter)
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
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if len(stroke.points) == 1:
            first_point = stroke.points[0]
            pen = QPen(QColor(stroke.color), first_point.pressure)
            painter.setPen(pen)
            painter.drawPoint(QPointF(first_point.x, first_point.y))
            return

        for i in range(len(stroke.points) - 1):
            p1 = stroke.points[i]
            p2 = stroke.points[i + 1]
            avg_pressure = (p1.pressure + p2.pressure) / 2
            width = avg_pressure * self.base_thickness * 2

            path: QPainterPath = QPainterPath()
            path.moveTo(p1.x, p1.y)

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

        if len(self.current_stroke.points) >= 2:
            last_point = self.current_stroke.points[-2]
            current_point = self.current_stroke.points[-1]
            self.update_stroke_area(last_point, current_point, pressure)
        else:
            self.update()

    def update_stroke_area(self, p1: Point, p2: Point, pressure: float):
        """Update only the rectangular area containing the new stroke segment"""
        # Bounding box for the area
        width = pressure * self.base_thickness * 2
        margin = max(10, int(width) + 5)  # Some margin

        min_x = min(p1.x, p2.x) - margin
        min_y = min(p1.y, p2.y) - margin
        max_x = max(p1.x, p2.x) + margin
        max_y = max(p1.y, p2.y) + margin

        update_rect: QRect = QRect(
            int(min_x), int(min_y), int(max_x - min_x), int(max_y - min_y)
        )
        self.update(update_rect)

    def stop_drawing(self):
        """Stops current stroke"""
        self.is_drawing = False
        if self.current_stroke is None:
            return
        self.page.strokes.append(self.current_stroke)

        # Render the completed stroke to the backing pixmap
        if self.backing_pixmap:
            painter = QPainter(self.backing_pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            self.draw_stroke(self.current_stroke, painter)
            _ = painter.end()

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
            if self.is_drawing:
                self.stop_drawing()
        event.accept()

    @override
    def resizeEvent(self, a0: QResizeEvent | None):
        """Invalidate the pixmap"""
        super().resizeEvent(a0)
        self.needs_full_redraw = True
