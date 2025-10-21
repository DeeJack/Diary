"""Represents a Widget for the Page inside the Notebook"""

import logging
from typing import override
from datetime import datetime


from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from PyQt6 import QtGui
from PyQt6.QtGui import (
    QFont,
    QPainter,
    QColor,
    QPaintEvent,
    QBrush,
    QPointingDevice,
    QTabletEvent,
    QPixmap,
    QResizeEvent,
)
from PyQt6.QtCore import QPointF, Qt, QRect, pyqtSignal

from diary.models.page import Page
from diary.config import settings
from diary.models.point import Point
from diary.models.stroke import Stroke
from diary.models.page_element import PageElement
from diary.ui.adapters import adapter_registry
from diary.ui.adapters.stroke_adapter import StrokeAdapter
from diary.ui.adapters.image_adapter import ImageAdapter
from diary.ui.adapters.voice_memo_adapter import VoiceMemoAdapter


class PageWidget(QWidget):
    """Represents the UI of a Page in the Notebook"""

    add_below: pyqtSignal = pyqtSignal(object)
    add_below_dynamic: pyqtSignal = pyqtSignal(object)
    needs_regeneration: pyqtSignal = pyqtSignal(int)

    def __init__(self, page: Page | None, page_index: int):
        super().__init__()
        self.page_width: int = settings.PAGE_WIDTH
        self.page_height: int = settings.PAGE_HEIGHT
        self.current_stroke: Stroke | None = None
        self.page: Page = page or Page()
        self.is_drawing: bool = False
        self.is_erasing: bool = False
        self.base_thickness: float = 3.0
        self.needs_full_redraw: bool = True
        self.backing_pixmap: QPixmap | None = None
        self.logger: logging.Logger = logging.getLogger("PageWidget")
        self.is_loaded: bool = False
        self.page_index: int = page_index

        self.setFixedSize(self.page_width, self.page_height)
        self.setMinimumWidth(self.page_width)

        # Initialize adapters
        self._setup_adapters()

        self.add_page_items()

    def _setup_adapters(self):
        """Setup the element adapters for rendering"""
        # Register all available adapters
        stroke_adapter = StrokeAdapter(self.base_thickness)
        image_adapter = ImageAdapter()
        voice_memo_adapter = VoiceMemoAdapter()

        adapter_registry.register(stroke_adapter)
        adapter_registry.register(image_adapter)
        adapter_registry.register(voice_memo_adapter)

    def add_page_items(self):
        """Adds the labels and buttons to the Page"""
        date: str = datetime.fromtimestamp(self.page.created_at).strftime("%Y-%m-%d")
        title_label = QLabel(date)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setFont(QFont("Times New Roman", 16))
        title_label.setStyleSheet("color:black;")

        btn_below = QPushButton("Add below")
        _ = btn_below.clicked.connect(lambda: self.add_below.emit(self))

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(btn_below)
        btn_row.addStretch()

        main = QVBoxLayout(self)
        main.addWidget(title_label)
        main.addStretch()
        main.addLayout(btn_row)
        main.setContentsMargins(10, 10, 10, 10)

    def ensure_backing_pixmap(self):
        """Initialize or resize the backing pixmap if needed"""
        if self.backing_pixmap is None or self.backing_pixmap.size() != self.size():
            self.backing_pixmap = QPixmap(self.size())
            self.needs_full_redraw = True

    def render_backing_pixmap(self):
        """Render the background and all previous strokes to the pixmap"""
        if not self.backing_pixmap:
            return

        painter = QPainter(self.backing_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.backing_pixmap.rect(), QColor(0xE0, 0xE0, 0xE0))
        self.draw_horizontal_lines(painter)
        self.draw_previous_elements(painter)
        _ = painter.end()
        self.needs_full_redraw = False

    @override
    def paintEvent(self, a0: QPaintEvent | None) -> None:
        """Draw the pixmap and current stroke"""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        if self.is_loaded and self.backing_pixmap:
            painter.drawPixmap(0, 0, self.backing_pixmap)
        else:
            # Draw a placeholder until loaded
            painter.fillRect(self.rect(), QColor(0xF0, 0xF0, 0xF0))

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

    def draw_element(self, element: PageElement, painter: QPainter):
        """Draw an element using the appropriate adapter"""
        if not adapter_registry.render_element(element, painter):
            self.logger.warning(
                f"No adapter found for element type: {element.element_type}"
            )

    def draw_current_stroke(self, painter: QPainter):
        """Draw the current stroke on the page"""
        if self.current_stroke is not None:
            self.draw_element(self.current_stroke, painter)

    def draw_previous_elements(self, painter: QPainter):
        """Draw the elements that have already been saved"""
        for element in self.page.elements:
            self.draw_element(element, painter)

    def continue_drawing(self, event: QTabletEvent, pos: QPointF):
        """Continues current stroke"""
        if self.current_stroke is None:
            self.current_stroke = Stroke()
        pressure = event.pressure()
        self.current_stroke.points.append(Point(pos.x(), pos.y(), pressure))

        if len(self.current_stroke.points) >= 2:
            last_point = self.current_stroke.points[-2]
            current_point = self.current_stroke.points[-1]
            self.update_stroke_area(last_point, current_point)
        else:
            self.update()

    def update_stroke_area(self, p1: Point, p2: Point):
        """Update only the rectangular area containing the new stroke segment"""
        # Calculate the bounding rectangle for this stroke segment
        avg_pressure = (p1.pressure + p2.pressure) / 2
        width = self.calculate_width_from_pressure(avg_pressure)
        margin = max(10, int(width) + 5)  # Add some margin for antialiasing

        min_x = min(p1.x, p2.x) - margin
        min_y = min(p1.y, p2.y) - margin
        max_x = max(p1.x, p2.x) + margin
        max_y = max(p1.y, p2.y) + margin

        update_rect = QRect(
            int(min_x), int(min_y), int(max_x - min_x), int(max_y - min_y)
        )
        self.update(update_rect)

    def stop_drawing(self, position: QPointF):
        """Stops current stroke and adds it to backing pixmap"""
        self.is_drawing = False
        if self.current_stroke is None:
            return
        self.page.add_element(self.current_stroke)

        # Render the completed stroke to the backing pixmap
        if self.backing_pixmap:
            painter = QPainter(self.backing_pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            self.draw_element(self.current_stroke, painter)
            _ = painter.end()

        self.current_stroke = None
        self.update()

        if position.y() > (float(self.height()) / 10 * 8):
            self.add_below_dynamic.emit(self)

    def erase(self, pos: QPointF):
        CIRCLE_RADIUS = 4  # 3 pixels circle
        element_to_remove: Stroke | None = None

        for element in self.page.elements.copy():
            if isinstance(element, Stroke) and element.intersects(
                Point(pos.x(), pos.y(), 0), CIRCLE_RADIUS
            ):
                self.logger.debug("Erasing element %s", element.element_id)
                element_to_remove = element
                break

        if element_to_remove:
            if self.backing_pixmap:
                painter = QPainter(self.backing_pixmap)

                # Get the bounding box of the stroke to erase
                bounding_rect = StrokeAdapter.stroke_to_bounding_rect(element_to_remove)
                # Add a small margin for anti-aliasing
                bounding_rect = bounding_rect.adjusted(-5, -5, 5, 5)

                # "Erase" by painting the background color over the area
                painter.fillRect(bounding_rect, QColor(0xE0, 0xE0, 0xE0))

                # OPTIONAL BUT RECOMMENDED: Redraw the page lines in this area
                # This prevents leaving blank spots where lines should be
                painter.setBrush(QBrush(QColor(0xDD, 0xCD, 0xC4)))
                painter.setPen(QColor(0xDD, 0xCD, 0xC4))
                painter.setOpacity(0.9)
                for line_y in range(
                    int(bounding_rect.top()),
                    int(bounding_rect.bottom()),
                    settings.PAGE_LINES_SPACING,
                ):
                    if (
                        line_y >= settings.PAGE_LINES_SPACING
                    ):  # Avoid drawing on top margin
                        painter.drawLine(
                            QPointF(bounding_rect.left(), float(line_y)),
                            QPointF(bounding_rect.right(), float(line_y)),
                        )

                _ = painter.end()

            # --- DATA & REGENERATION ---
            self.page.remove_element(element_to_remove)

            # Immediately update the screen with the "dirty" pixmap
            self.update()

            # Tell the Notebook to start a proper re-render in the background
            self.needs_regeneration.emit(self.page_index)

    def handle_tablet_event(self, event: QTabletEvent, pos: QPointF):
        """Handles Pen events, forwarded by the Notebook"""
        if event.pointerType() == QPointingDevice.PointerType.Pen:
            if event.type() == QTabletEvent.Type.TabletPress:
                self.is_drawing = True
                self.current_stroke = Stroke()
            elif event.type() == QTabletEvent.Type.TabletMove:
                if self.is_drawing:
                    self.continue_drawing(event, pos)
            elif event.type() == QTabletEvent.Type.TabletRelease:
                if self.is_drawing:
                    self.stop_drawing(pos)
        elif event.pointerType() == QPointingDevice.PointerType.Eraser:
            if event.type() == QTabletEvent.Type.TabletPress:
                self.is_erasing = True
            elif event.type() == QTabletEvent.Type.TabletMove:
                if self.is_erasing:
                    self.erase(pos)
            elif event.type() == QTabletEvent.Type.TabletRelease:
                self.is_erasing = False
        event.accept()

    @override
    def resizeEvent(self, a0: QResizeEvent | None):
        """Handle widget resize by invalidating backing pixmap"""
        super().resizeEvent(a0)
        self.needs_full_redraw = True

    def clear_page(self):
        """Clear all elements and force a full redraw"""
        self.logger.debug("Clearing page")
        self.page.clear_elements()
        self.current_stroke = None
        self.needs_full_redraw = True
        self.update()

    def calculate_width_from_pressure(self, pressure: float) -> float:
        """Calculate stroke width based on pressure"""
        # Pressure ranges from 0.0 to 1.0
        min_width = 1.0
        max_width = self.base_thickness * 2
        return min_width + (pressure * (max_width - min_width))

    def set_backing_pixmap(self, pixmap: QPixmap):
        """
        Sets the backing pixmap and triggers a reload.
        """
        self.backing_pixmap = pixmap
        self.is_loaded = True
        self.needs_full_redraw = False
        self.update()
