from typing import Optional

from PyQt6.QtWidgets import QWidget
from PyQt6 import QtGui
from PyQt6.QtGui import QPainter, QColor, QPaintEvent, QBrush, QPainterPath

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
