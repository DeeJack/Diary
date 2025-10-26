"""Represents a Widget for the Page inside the Notebook"""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import override

from PyQt6 import QtGui
from PyQt6.QtCore import QPointF, QRect, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPixmap,
    QResizeEvent,
    QTabletEvent,
    QTouchEvent,
)
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from diary.config import settings
from diary.models import Image, Page, PageElement, Point, Stroke, Text
from diary.ui.adapters import adapter_registry
from diary.ui.adapters.image_adapter import ImageAdapter
from diary.ui.adapters.stroke_adapter import StrokeAdapter
from diary.ui.adapters.text_adapter import TextAdapter
from diary.ui.adapters.voice_memo_adapter import VoiceMemoAdapter
from diary.ui.widgets.tool_selector import Tool


class InputType(Enum):
    """Type of input device"""

    TABLET = "tablet"
    MOUSE = "mouse"
    TOUCH = "touch"


class InputAction(Enum):
    """Type of input action"""

    PRESS = "press"
    MOVE = "move"
    RELEASE = "release"


@dataclass
class DrawingInput:
    """Generic input event for drawing operations"""

    position: QPointF
    action: InputAction
    input_type: InputType
    pressure: float = 1.0  # 0.0 to 1.0, default 1.0 for mouse/touch
    tilt_x: float = 0.0  # -1.0 to 1.0, tablet only
    tilt_y: float = 0.0  # -1.0 to 1.0, tablet only
    rotation: float = 0.0  # 0.0 to 360.0, tablet only


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
        self.base_thickness: float = 2.0
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
        stroke_adapter = StrokeAdapter(base_thickness=3.0)
        image_adapter = ImageAdapter()
        voice_memo_adapter = VoiceMemoAdapter()
        text_adapter = TextAdapter()

        adapter_registry.register(stroke_adapter)
        adapter_registry.register(image_adapter)
        adapter_registry.register(voice_memo_adapter)
        adapter_registry.register(text_adapter)

    def add_page_items(self):
        """Adds the labels and buttons to the Page"""
        date: str = datetime.fromtimestamp(self.page.created_at).strftime("%Y-%m-%d")
        title = (
            date
            if self.page.streak_lvl == 0
            else f"{date} (Streak: {self.page.streak_lvl})"
        )
        title_label = QLabel(title)
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
        rendering_scale = settings.RENDERING_SCALE
        expected_size = self.size() * rendering_scale

        if (
            self.backing_pixmap is None
            or self.backing_pixmap.size() != expected_size
            or abs(self.backing_pixmap.devicePixelRatio() - rendering_scale) > 0.01
        ):
            # Create high-resolution pixmap for crisp scaling
            high_res_width = int(self.size().width() * rendering_scale)
            high_res_height = int(self.size().height() * rendering_scale)

            self.backing_pixmap = QPixmap(high_res_width, high_res_height)
            # Set device pixel ratio to match our rendering scale
            self.backing_pixmap.setDevicePixelRatio(rendering_scale)
            self.needs_full_redraw = True

    def render_backing_pixmap(self):
        """Render the background and all previous strokes to the pixmap"""
        if not self.backing_pixmap:
            return

        painter = QPainter(self.backing_pixmap)
        # Enable high-quality rendering hints for crisp strokes
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        # Scale the painter to render at high resolution
        rendering_scale = settings.RENDERING_SCALE
        painter.scale(rendering_scale, rendering_scale)

        painter.fillRect(
            QRect(0, 0, self.page_width, self.page_height), QColor(0xE0, 0xE0, 0xE0)
        )
        self.draw_horizontal_lines(painter)
        self.draw_previous_elements(painter)
        _ = painter.end()
        self.needs_full_redraw = False

    @override
    def paintEvent(self, a0: QPaintEvent | None) -> None:
        """Draw the pixmap and current stroke"""
        self.ensure_backing_pixmap()

        painter = QtGui.QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        if self.is_loaded and self.backing_pixmap:
            painter.drawPixmap(0, 0, self.backing_pixmap)
        else:
            # Draw a placeholder until loaded
            painter.fillRect(self.rect(), QColor(0xF0, 0xF0, 0xF0))

            # If we have a backing pixmap but content hasn't loaded yet, render it
            if self.backing_pixmap and self.needs_full_redraw:
                self.render_backing_pixmap()

            painter.setFont(QFont("Times New Roman", 50))
            painter.setPen(QColor(0x80, 0x80, 0x80))  # A medium grey color
            _ = painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "Loading...",
            )

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
                "No adapter found for element type: %s", element.element_type
            )

    def draw_current_stroke(self, painter: QPainter):
        """Draw the current stroke on the page"""
        if self.current_stroke is not None:
            self.draw_element(self.current_stroke, painter)

    def draw_previous_elements(self, painter: QPainter):
        """Draw the elements that have already been saved"""
        for element in self.page.elements:
            self.draw_element(element, painter)

    def _start_drawing(self, _: DrawingInput, color: QColor):
        """Starts a new drawing stroke"""
        self.is_drawing = True
        self.current_stroke = Stroke(color=color.name())

    def _continue_drawing(self, drawing_input: DrawingInput, current_width: float):
        """Continues current stroke"""
        self.logger.debug("Drawing %s", drawing_input)
        if self.current_stroke is None:
            self.current_stroke = Stroke()
        width = self.calculate_width_from_pressure(
            drawing_input.pressure, current_width, drawing_input.input_type
        )
        self.current_stroke.points.append(
            Point(drawing_input.position.x(), drawing_input.position.y(), width)
        )

        if len(self.current_stroke.points) >= 2:
            last_point = self.current_stroke.points[-2]
            current_point = self.current_stroke.points[-1]
            self.update_stroke_area(last_point, current_point, current_width)
        else:
            self.update()

    def _stop_drawing(self, drawing_input: DrawingInput):
        """Stops current stroke and adds it to backing pixmap"""
        self.is_drawing = False
        if self.current_stroke is None:
            return
        # drawing_input.position could be used for final stroke point
        self.current_stroke.points = smooth_stroke_moving_average(
            self.current_stroke.points, 8
        )
        self.page.add_element(self.current_stroke)

        # Render the completed stroke to the backing pixmap
        self.ensure_backing_pixmap()
        if self.backing_pixmap:
            painter = QPainter(self.backing_pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
            self.draw_element(self.current_stroke, painter)
            _ = painter.end()

        self.current_stroke = None
        self.update()

    def _handle_drawing_input(
        self,
        drawing_input: DrawingInput,
    ):
        """Generic drawing input handler that works with any input type"""
        if settings.CURRENT_TOOL == Tool.ERASER:
            if drawing_input.action == InputAction.PRESS:
                self.is_erasing = True
            elif drawing_input.action == InputAction.MOVE:
                if self.is_erasing:
                    self.erase(drawing_input.position)
            elif drawing_input.action == InputAction.RELEASE:
                self.is_erasing = False
        elif settings.CURRENT_TOOL == Tool.PEN:
            if drawing_input.action == InputAction.PRESS:
                self._start_drawing(drawing_input, settings.CURRENT_COLOR)
            elif drawing_input.action == InputAction.MOVE:
                if self.is_drawing:
                    self._continue_drawing(drawing_input, settings.CURRENT_WIDTH)
            elif drawing_input.action == InputAction.RELEASE:
                if self.is_drawing:
                    self._stop_drawing(drawing_input)

    def continue_drawing(self, event: QTabletEvent, pos: QPointF, current_width: float):
        """Legacy method - continues current stroke (deprecated, use _continue_drawing)"""
        if self.current_stroke is None:
            self.current_stroke = Stroke()
        width = self.calculate_width_from_pressure(event.pressure(), current_width)
        self.current_stroke.points.append(Point(pos.x(), pos.y(), width))

        if len(self.current_stroke.points) >= 2:
            last_point = self.current_stroke.points[-2]
            current_point = self.current_stroke.points[-1]
            self.update_stroke_area(last_point, current_point, current_width)
        else:
            self.update()

    def update_stroke_area(self, p1: Point, p2: Point, current_width: float):
        """Update only the rectangular area containing the new stroke segment"""
        # Calculate the bounding rectangle for this stroke segment
        avg_pressure = (p1.pressure + p2.pressure) / 2
        width = self.calculate_width_from_pressure(avg_pressure, current_width)
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
        """Legacy method - stops current stroke (deprecated, use _stop_drawing)"""
        self.is_drawing = False
        if self.current_stroke is None:
            return
        self.current_stroke.points = smooth_stroke_moving_average(
            self.current_stroke.points, 8
        )
        self.page.add_element(self.current_stroke)

        # Render the completed stroke to the backing pixmap
        self.ensure_backing_pixmap()
        if self.backing_pixmap:
            painter = QPainter(self.backing_pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
            self.draw_element(self.current_stroke, painter)
            _ = painter.end()

        self.current_stroke = None
        self.update()

        if position.y() > (float(self.height()) / 10 * 8):
            self.add_below_dynamic.emit(self)

    def erase(self, pos: QPointF):
        """Erase strokes intersecting with the given position"""
        CIRCLE_RADIUS = 4  # pixels
        elements_to_remove: list[PageElement] = []

        for element in self.page.elements.copy():
            if element.intersects(Point(pos.x(), pos.y(), 0), CIRCLE_RADIUS):
                self.logger.debug("Erasing element %s", element.element_id)
                elements_to_remove.append(element)

        self.ensure_backing_pixmap()
        if self.backing_pixmap:
            painter = QPainter(self.backing_pixmap)

            for element_to_remove in elements_to_remove:
                self.page.remove_element(element_to_remove)

                # Get the bounding box of the stroke to erase
                bounding_rect: QRectF = adapter_registry.get_adapter(
                    element_to_remove
                ).rect(element_to_remove)

                # "Erase" by painting the background color over the area
                painter.fillRect(bounding_rect, QColor(0xE0, 0xE0, 0xE0))
            _ = painter.end()

        if len(elements_to_remove) > 0:
            self.update()
            self.needs_regeneration.emit(self.page_index)

    def handle_tablet_event(
        self,
        event: QTabletEvent,
        pos: QPointF,
    ):
        """Handles tablet pen events, forwarded by the Notebook"""
        # Convert tablet event to generic drawing input
        action = InputAction.PRESS
        if event.type() == QTabletEvent.Type.TabletMove:
            action = InputAction.MOVE
        elif event.type() == QTabletEvent.Type.TabletRelease:
            action = InputAction.RELEASE

        drawing_input = DrawingInput(
            position=pos,
            action=action,
            input_type=InputType.TABLET,
            pressure=event.pressure(),
            tilt_x=event.xTilt(),
            tilt_y=event.yTilt(),
            rotation=event.rotation(),
        )

        self._handle_drawing_input(drawing_input)
        event.accept()

    def handle_touch_event(
        self,
        _: QTouchEvent,
        pos: QPointF,
        touch_action: InputAction,
    ):
        """Handles touch events for drawing"""
        drawing_input = DrawingInput(
            position=pos,
            action=touch_action,
            input_type=InputType.TOUCH,
            pressure=1.0,
        )
        self._handle_drawing_input(drawing_input)

    @override
    def resizeEvent(self, a0: QResizeEvent | None):
        """Handle widget resize by invalidating backing pixmap"""
        super().resizeEvent(a0)
        self.needs_full_redraw = True

    def calculate_width_from_pressure(
        self,
        pressure: float,
        current_width: float,
        input_type: InputType = InputType.TABLET,
    ) -> float:
        """Calculate stroke width based on pressure and input type"""
        # Pressure ranges from 0.0 to 1.0
        min_width = 1.5
        max_width = current_width * 3

        if settings.USE_PRESSURE and input_type == InputType.TABLET:
            return min_width + (pressure * (max_width - min_width))

        return current_width

    def set_backing_pixmap(self, pixmap: QPixmap):
        """
        Sets the backing pixmap and triggers a reload.
        """
        self.backing_pixmap = pixmap
        if self.backing_pixmap:
            self.backing_pixmap.setDevicePixelRatio(settings.RENDERING_SCALE)
        self.is_loaded = True
        self.needs_full_redraw = False
        self.update()

    def handle_mouse_event(self, event: QMouseEvent, position: QPointF):
        """Handle a mouse event inside the page"""
        if not event or not settings.MOUSE_ENABLED:
            return
        action = InputAction.PRESS
        if event.type() == QMouseEvent.Type.MouseButtonRelease:
            action = InputAction.RELEASE
        elif event.type() == QMouseEvent.Type.MouseMove:
            action = InputAction.MOVE
        drawing_input = DrawingInput(
            position=position,
            action=action,
            input_type=InputType.MOUSE,
            pressure=1.0,
        )
        if settings.CURRENT_TOOL in [Tool.PEN, Tool.ERASER]:
            self._handle_drawing_input(drawing_input)
            event.accept()
        elif settings.CURRENT_TOOL == Tool.TEXT and action == InputAction.PRESS:
            self._add_text_element(Point(position.x(), position.y()))
        elif settings.CURRENT_TOOL == Tool.IMAGE and action == InputAction.PRESS:
            self._add_image_element(Point(position.x(), position.y()))

    def _add_text_element(self, pos: Point):
        """Ask for the text to insert, and add a text element to the cursor's position"""
        text, ok = QInputDialog.getText(
            self.parentWidget(),
            "Insert text",
            "Text to add",
        )
        if not ok:
            return
        self.page.elements.append(Text(text, pos))
        self.needs_full_redraw = True
        self.needs_regeneration.emit(self.page_index)

    def _add_image_element(self, pos: Point):
        image_file, _ = QFileDialog.getOpenFileName(
            self.parentWidget(),
            "Select image",
            filter=("Images (*.png *.xpm *.jpg *.jpeg *.webp)"),
        )
        self.logger.debug("Selected image: %s", image_file)
        if not image_file:
            return
        image_bytes = Image.read_bytes_from_file(Path(image_file))
        image = Image(pos, width=100, height=100, image_data=image_bytes)
        self.logger.debug("Saving image with data: %s", image_bytes)
        self.page.elements.append(image)
        self.needs_full_redraw = True
        self.needs_regeneration.emit(self.page_index)


def smooth_stroke_moving_average(
    stroke_points: list[Point], window_size: int = 4
) -> list[Point]:
    """
    Smooths a stroke using a simple moving average filter.
    """
    if len(stroke_points) < window_size:
        return stroke_points  # Not enough points to smooth, return as is

    smoothed_points = []
    # Start with the first few points to avoid a harsh jump
    for i in range(window_size):
        smoothed_points.append(stroke_points[i])

    for i in range(window_size, len(stroke_points)):
        # Get the slice of points for the moving average window
        window = stroke_points[i - window_size : i]

        # Calculate the average x, y, and pressure
        avg_x = sum(p.x for p in window) / window_size
        avg_y = sum(p.y for p in window) / window_size
        avg_pressure = sum(p.pressure for p in window) / window_size

        smoothed_points.append(Point(avg_x, avg_y, avg_pressure))

    return smoothed_points
