from typing import Optional

from PyQt6.QtWidgets import QWidget
from PyQt6 import QtGui
from PyQt6.QtGui import (
    QPainter,
    QColor,
    QPaintEvent,
    QBrush,
    QTabletEvent,
)
from PyQt6.QtCore import QPoint, Qt

from diary.models.page import Page
from diary.config import settings
from diary.models.stroke import Stroke


class PageWidget(QWidget):
    def __init__(self, page: Page = Page()):
        super().__init__()
        self.page_width = settings.PAGE_WIDTH
        self.page_height = settings.PAGE_HEIGHT

        self.setFixedSize(self.page_width, self.page_height)
        self.setMinimumWidth(self.page_width)

        self.current_stroke = []
        self.page = page

        self.is_drawing = False

    def paintEvent(self, a0: Optional[QPaintEvent]) -> None:
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(0xE0, 0xE0, 0xE0))

        self.draw_horizontal_lines(painter)

        return super().paintEvent(a0)

    def draw_stroke(self, stroke: Stroke):
        pass

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

    def draw_previous_strokes(self):
        for stroke in self.page.strokes:
            self.draw_stroke(stroke)

    def start_drawing(self, event):
        pass

    def continue_drawing(self, event):
        pass

    def stop_drawing(self, event):
        pass

    def handle_tablet_event(self, event: QTabletEvent, pos: QPoint):
        """This should now receive events!"""
        print(f"Page received tablet event: {event.position()}")

        if event.type() == QTabletEvent.Type.TabletPress:
            # event.position() is already in widget coordinates
            self.is_drawing = True
            self.current_stroke = []

        elif event.type() == QTabletEvent.Type.TabletMove:
            if self.is_drawing:
                pos = event.position()
                pressure = event.pressure()
                self.current_stroke.append((pos.x(), pos.y(), pressure))
                self.update()

        elif event.type() == QTabletEvent.Type.TabletRelease:
            self.is_drawing = False
            # self.page.elements.append(Stroke(self.current_stroke))
            self.update()

        event.accept()
