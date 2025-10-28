"""Graphics widget for diary pages"""

import logging
from datetime import datetime
from typing import override

from PyQt6.QtCore import QPointF, Qt, pyqtSignal
from PyQt6.QtGui import QFont, QMouseEvent, QPainter, QPointingDevice, QTabletEvent
from PyQt6.QtWidgets import (
    QFileDialog,
    QGraphicsView,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from diary.config import settings
from diary.models import PageElement
from diary.models.elements.stroke import Stroke
from diary.models.elements.text import Text
from diary.models.page import Page
from diary.models.point import Point
from diary.ui.adapters.image_adapter import ImageAdapter
from diary.ui.input import InputAction, InputType
from diary.ui.widgets.tool_selector import Tool

from .page_graphics_scene import PageGraphicsScene
from .stroke_graphics_item import StrokeGraphicsItem


class PageGraphicsWidget(QWidget):
    """Widget for displaying diary pages using QGraphicsItem architecture"""

    add_below: pyqtSignal = pyqtSignal(object)
    add_below_dynamic: pyqtSignal = pyqtSignal(object)
    needs_regeneration: pyqtSignal = pyqtSignal(int)
    page_modified: pyqtSignal = pyqtSignal()

    def __init__(self, page: Page, page_index: int):
        super().__init__()

        self.page_index: int = page_index
        self._current_stroke: Stroke | None = None
        self._current_stroke_item: StrokeGraphicsItem | None = None
        self._is_drawing: bool = False
        self._logger: logging.Logger = logging.getLogger("PageGraphicsWidget")

        # Create the graphics scene and view
        self._scene: PageGraphicsScene = PageGraphicsScene(page)
        self._graphics_view: QGraphicsView = QGraphicsView(self._scene)

        # Configure the graphics view
        self._setup_graphics_view()

        # Connect scene signals
        _ = self._scene.page_modified.connect(self.page_modified.emit)
        _ = self._scene.element_added.connect(lambda elem: self.page_modified.emit())
        _ = self._scene.element_removed.connect(
            lambda elem_id: self.page_modified.emit()
        )

        self._setup_layout()

        # Configure widget properties
        self.setFixedSize(settings.PAGE_WIDTH, settings.PAGE_HEIGHT)

        self._logger.debug(f"Created PageGraphicsWidget for page {page_index}")

    @property
    def page(self) -> Page:
        """Get the current page"""
        return self._scene.page

    @page.setter
    def page(self, value: Page) -> None:
        """Set the page"""
        self._scene.page = value

    @property
    def scene(self) -> PageGraphicsScene:
        """Get the graphics scene"""
        return self._scene

    @property
    def graphics_view(self) -> QGraphicsView:
        """Get the graphics view"""
        return self._graphics_view

    def _setup_graphics_view(self) -> None:
        """Configure the QGraphicsView"""
        # Disable scrollbars since this will be managed by the parent NotebookWidget
        self._graphics_view.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._graphics_view.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        # Configure view properties
        self._graphics_view.setDragMode(QGraphicsView.DragMode.NoDrag)
        self._graphics_view.setInteractive(True)
        self._graphics_view.setMouseTracking(True)

        # Enable high-quality rendering
        self._graphics_view.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self._graphics_view.setRenderHint(
            QPainter.RenderHint.SmoothPixmapTransform, True
        )
        self._graphics_view.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        # Set fixed size to match page dimensions
        self._graphics_view.setFixedSize(settings.PAGE_WIDTH, settings.PAGE_HEIGHT)

    def _setup_layout(self) -> None:
        """Setup the widget layout with page info and controls"""
        # Create page title
        page_date = datetime.fromtimestamp(
            self.page.created_at if self.page else 0
        ).strftime("%Y-%m-%d")
        streak_info = ""
        if self.page and self.page.streak_lvl > 0:
            streak_info = f" (Streak: {self.page.streak_lvl})"

        title = f"{page_date}{streak_info}"
        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setFont(QFont("Times New Roman", 16))
        title_label.setStyleSheet("color: black;")

        # Create "Add below" button
        btn_below = QPushButton("Add below")
        btn_below.setAttribute(Qt.WidgetAttribute.WA_NoMousePropagation, True)
        _ = btn_below.clicked.connect(lambda: self.add_below.emit(self))

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(btn_below)
        btn_row.addStretch()

        # Main layout
        main_layout = QGridLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self._graphics_view, 0, 0)

        # Create an overlay layout for the title and button
        overlay_layout = QVBoxLayout()
        overlay_layout.addWidget(title_label)
        overlay_layout.addStretch()
        overlay_layout.addLayout(btn_row)
        overlay_layout.setContentsMargins(0, 10, 0, 10)

        # Add the overlay layout to the same grid cell (0, 0)
        main_layout.addLayout(overlay_layout, 0, 0)
        btn_below.raise_()

    def handle_drawing_input(
        self,
        position: QPointF,
        pressure: float = 1.0,
        action: InputAction = InputAction.PRESS,
        device: InputType = InputType.MOUSE,
        is_eraser: bool = False,
    ) -> None:
        """Handle drawing input from mouse, tablet, or touch"""
        current_tool = settings.CURRENT_TOOL

        if current_tool == Tool.PEN and not is_eraser:
            self._handle_pen_input(position, pressure, action, device)
        elif current_tool == Tool.TEXT:
            self._handle_text_input(position, action)
        elif current_tool == Tool.ERASER or is_eraser:
            self._handle_eraser_input(position, action)
        elif current_tool == Tool.IMAGE:
            self._handle_image_input(position, action)

    def _handle_pen_input(
        self, position: QPointF, pressure: float, action: InputAction, device: InputType
    ) -> None:
        """Handle pen/drawing input"""
        match action:
            case InputAction.PRESS:
                self._start_new_stroke(position, pressure)
            case InputAction.MOVE:
                self._add_stroke_point(position, pressure)
            case InputAction.RELEASE:
                self._finish_current_stroke(device)

    def _handle_text_input(self, position: QPointF, action: InputAction) -> None:
        """Handle text input"""
        if action == InputAction.PRESS:
            # Create new text element at click position
            scene_pos = self._graphics_view.mapToScene(position.toPoint())
            point = Point(scene_pos.x(), scene_pos.y(), 1.0)

            # TODO: Type without opening a dialog
            text, ok = QInputDialog.getText(
                self.parentWidget(),
                "Insert text",
                "Text to add",
            )
            if not ok:
                return

            text_element = self._scene.create_text(
                text=text, position=point, color="black", size_px=20.0
            )

            if text_element:
                self._logger.debug(f"Created text element at {scene_pos}")

    def _handle_eraser_input(self, position: QPointF, action: InputAction) -> None:
        """Handle eraser input"""
        if action in [InputAction.PRESS, InputAction.MOVE]:
            # Find and remove elements at position
            scene_pos = self._graphics_view.mapToScene(position.toPoint())
            elements = self._scene.get_elements_at_point(scene_pos)

            for element in elements:
                if isinstance(element, (Stroke, Text)):
                    _ = self._scene.remove_element(element.element_id)
                    self._logger.debug(f"Erased element {element.element_id}")

    def _start_new_stroke(self, position: QPointF, pressure: float) -> None:
        """Start a new stroke"""
        scene_pos = self._graphics_view.mapToScene(position.toPoint())
        point = Point(scene_pos.x(), scene_pos.y(), pressure)

        # Get current drawing settings
        color = settings.CURRENT_COLOR
        thickness = settings.CURRENT_WIDTH

        # Create new stroke
        self._current_stroke = Stroke(
            points=[point], color=color.name(), size=thickness, tool="pen"
        )

        # Add to scene and get graphics item
        graphics_item = self._scene.add_element(self._current_stroke)
        if isinstance(graphics_item, StrokeGraphicsItem):
            self._current_stroke_item = graphics_item

        self._is_drawing = True
        self._logger.debug(f"Started new stroke at {scene_pos}")

    def _add_stroke_point(self, position: QPointF, pressure: float) -> None:
        """Add a point to the current stroke"""
        if (
            not self._current_stroke
            or not self._current_stroke_item
            or not self._is_drawing
        ):
            return

        scene_pos = self._graphics_view.mapToScene(position.toPoint())
        point = Point(scene_pos.x(), scene_pos.y(), pressure)

        # Add point to graphics item (which updates the stroke)
        self._current_stroke_item.add_point(point)

    def _finish_current_stroke(self, device: InputType) -> None:
        """Finish the current stroke"""
        if self._current_stroke:
            self._logger.debug(
                f"Finished stroke with {len(self._current_stroke.points)} points"
            )

            if device == InputType.TABLET:
                self._current_stroke.points = smooth_stroke_moving_average(
                    self._current_stroke.points, 8
                )

        self._current_stroke = None
        self._current_stroke_item = None
        self._is_drawing = False

    def handle_mouse_event(self, event: QMouseEvent, pos: QPointF) -> None:
        """Handle mouse move events"""
        action = InputAction.PRESS
        if event.type() == QMouseEvent.Type.MouseMove:
            action = InputAction.MOVE
        elif event.type() == QMouseEvent.Type.MouseButtonRelease:
            action = InputAction.RELEASE

        if event.buttons() & Qt.MouseButton.LeftButton:
            self.handle_drawing_input(pos, pressure=1.0, action=action)

    def handle_tablet_event(self, event: QTabletEvent, pos: QPointF) -> None:
        """Handle tablet events for pressure-sensitive input"""
        pressure = event.pressure() if event.pressure() > 0 else 1.0

        if event.type() == QTabletEvent.Type.TabletPress:
            action = InputAction.PRESS
        if event.type() == QTabletEvent.Type.TabletMove:
            action = InputAction.MOVE
        elif event.type() == QTabletEvent.Type.TabletRelease:
            action = InputAction.RELEASE
        else:
            return

        self.handle_drawing_input(
            pos,
            pressure=pressure,
            action=action,
            device=InputType.TABLET,
            is_eraser=event.pointerType() == QPointingDevice.PointerType.Eraser,
        )

    def _handle_image_input(self, position: QPointF, action: InputAction):
        """Handle input with Image tool"""
        if action == InputAction.PRESS:
            scene_pos = self._graphics_view.mapToScene(position.toPoint())
            point = Point(scene_pos.x(), scene_pos.y(), 1.0)

            image_file, _ = QFileDialog.getOpenFileName(
                self.parentWidget(),
                "Select image",
                filter=("Images (*.png *.xpm *.jpg *.jpeg *.webp)"),
            )
            self._logger.debug("Selected image: %s", image_file)
            if not image_file:
                return
            (image_bytes, height, width) = ImageAdapter.read_image(image_file)
            self._logger.debug(
                "Saving image with path: %s and data: %s...%s, height: %s, width: %s",
                image_file,
                image_bytes[:10],
                image_bytes[-10:],
                height,
                width,
            )
            _ = self._scene.create_image(
                point, width / 4, height / 4, image_data=image_bytes
            )

    def get_selected_elements(self) -> list[PageElement]:
        """Get currently selected elements"""
        return self._scene.get_selected_elements()

    def clear_selection(self) -> None:
        """Clear all selections"""
        self._scene.clearSelection()

    def select_all(self) -> None:
        """Select all elements"""
        for item in self._scene.items():
            item.setSelected(True)

    def delete_selected(self) -> None:
        """Delete all selected elements"""
        selected_elements = self.get_selected_elements()
        for element in selected_elements:
            _ = self._scene.remove_element(element.element_id)

    def get_scene_statistics(self) -> dict[str, int]:
        """Get statistics about the page contents"""
        return self._scene.get_scene_statistics()

    def zoom_to_fit(self) -> None:
        """Zoom the view to fit all content"""
        self._graphics_view.fitInView(
            self._scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio
        )

    def reset_zoom(self) -> None:
        """Reset zoom to fit the scene exactly"""
        self._graphics_view.fitInView(
            self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio
        )

    @override
    def __str__(self) -> str:
        """String representation"""
        stats = self.get_scene_statistics()
        return f"PageGraphicsWidget(index={self.page_index}, elements={stats['total_elements']})"

    @override
    def __repr__(self) -> str:
        """Detailed representation"""
        stats = self.get_scene_statistics()
        return (
            f"PageGraphicsWidget("
            f"index={self.page_index}, "
            f"elements={stats['total_elements']}, "
            f"strokes={stats['strokes']}, "
            f"texts={stats['texts']}, "
            f"images={stats['images']})"
        )


def smooth_stroke_moving_average(
    stroke_points: list[Point], window_size: int = 4
) -> list[Point]:
    """
    Smooths a stroke using a simple moving average filter.
    """
    if len(stroke_points) < window_size:
        return stroke_points  # Not enough points to smooth, return as is

    smoothed_points: list[Point] = []
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
