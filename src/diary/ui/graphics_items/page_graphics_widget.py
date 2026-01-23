"""Graphics widget for diary pages"""

import logging
from datetime import datetime
from typing import override

from PyQt6 import QtGui, QtWidgets
from PyQt6.QtCore import QEvent, QPointF, Qt, pyqtSignal

from diary.config import settings
from diary.models import PageElement
from diary.models.elements.stroke import Stroke
from diary.models.elements.text import Text
from diary.models.elements.video import Video
from diary.models.page import Page
from diary.models.point import Point
from diary.ui.input import InputAction, InputType
from diary.ui.ui_utils import (
    beautify_stroke,
    confirm_delete,
    generate_video_thumbnail,
    read_image,
    show_error_dialog,
    smooth_stroke_advanced,
)
from diary.ui.widgets.bottom_toolbar import BottomToolbar
from diary.ui.widgets.tool_selector import Tool

from .page_graphics_scene import PageGraphicsScene
from .stroke_graphics_item import StrokeGraphicsItem


class PageGraphicsWidget(QtWidgets.QWidget):
    """Widget for displaying diary pages using QGraphicsItem architecture"""

    add_below_dynamic: pyqtSignal = pyqtSignal()
    add_below: pyqtSignal = pyqtSignal(int)
    delete_page: pyqtSignal = pyqtSignal(int)
    needs_regeneration: pyqtSignal = pyqtSignal(int)
    page_modified: pyqtSignal = pyqtSignal()
    date_changed: pyqtSignal = pyqtSignal(int)  # Emits page_index when date is changed

    def __init__(self, page: Page, page_index: int, bottom_toolbar: BottomToolbar):
        super().__init__()

        self.page_index: int = page_index
        self._current_stroke: Stroke | None = None
        self._current_stroke_item: StrokeGraphicsItem | None = None
        self._is_drawing: bool = False
        self._is_erasing: bool = False
        self._logger: logging.Logger = logging.getLogger("PageGraphicsWidget")
        self._last_cursor: QtGui.QCursor = self.cursor()
        self._points_since_smooth: int = 0
        self._current_points: list[Point] = []
        self.bottom_toolbar: BottomToolbar = bottom_toolbar
        self._smoothed_points: list[Point] = []

        # Create the graphics scene and view
        self._scene: PageGraphicsScene = PageGraphicsScene(page)
        self._graphics_view: QtWidgets.QGraphicsView = QtWidgets.QGraphicsView(
            self._scene
        )

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

        self._logger.debug("Created PageGraphicsWidget for page %s", page_index)

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
    def graphics_view(self) -> QtWidgets.QGraphicsView:
        """Get the graphics view"""
        return self._graphics_view

    def cleanup(self) -> None:
        """Clean up resources before deletion to prevent memory leaks.

        This method disconnects all signals and clears the graphics scene
        to ensure proper cleanup of Qt objects and prevent segmentation faults.
        """
        self._logger.debug(
            "Cleaning up PageGraphicsWidget for page %s", self.page_index
        )

        # Disconnect signals to prevent callbacks to deleted objects
        try:
            self._scene.page_modified.disconnect()
            self._scene.element_added.disconnect()
            self._scene.element_removed.disconnect()
        except (TypeError, RuntimeError):
            pass  # Signals may already be disconnected

        # Clean up the scene
        self._scene.cleanup()

        # Clear references
        self._current_stroke = None
        self._current_stroke_item = None
        self._current_points.clear()
        self._smoothed_points.clear()

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
        self._graphics_view.setDragMode(QtWidgets.QGraphicsView.DragMode.NoDrag)
        self._graphics_view.setInteractive(True)
        self._graphics_view.setMouseTracking(True)

        # Enable high-quality rendering
        self._graphics_view.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        self._graphics_view.setRenderHint(
            QtGui.QPainter.RenderHint.SmoothPixmapTransform, True
        )
        self._graphics_view.setRenderHint(
            QtGui.QPainter.RenderHint.TextAntialiasing, True
        )

        # Set fixed size to match page dimensions
        self._graphics_view.setFixedSize(settings.PAGE_WIDTH, settings.PAGE_HEIGHT)

    def _setup_layout(self) -> None:
        """Setup the widget layout with page info and controls"""
        # Create page title
        page_date = datetime.fromtimestamp(
            self.page.created_at if self.page else 0
        ).strftime("%Y-%m-%d %a")
        streak_info = ""
        if self.page and self.page.streak_lvl > 0:
            streak_info = f" (Streak: {self.page.streak_lvl})"

        title = f"{page_date}{streak_info}"
        self.title_label: QtWidgets.QLabel = QtWidgets.QLabel(title)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setFont(QtGui.QFont("Times New Roman", 16))
        self.title_label.setStyleSheet("color: black;")

        # Create "Add below" button
        btn_below = QtWidgets.QPushButton("+")
        btn_below.setFont(QtGui.QFont("Times New Roman", 14, 16))
        btn_below.setAttribute(Qt.WidgetAttribute.WA_NoMousePropagation, True)
        btn_below.setFixedWidth(30)
        btn_below.setStyleSheet("background-color: #515151")
        btn_below.setToolTip("Add page below")
        _ = btn_below.clicked.connect(lambda: self.add_below.emit(self.page_index))

        change_date_btn = QtWidgets.QPushButton("📅")
        change_date_btn.setFont(QtGui.QFont("Times New Roman", 12))
        change_date_btn.setAttribute(Qt.WidgetAttribute.WA_NoMousePropagation, True)
        _ = change_date_btn.clicked.connect(self.change_date)
        change_date_btn.setFixedWidth(30)
        change_date_btn.setStyleSheet("background-color: #515151")
        change_date_btn.setToolTip("Change date")

        delete_btn = QtWidgets.QPushButton("🗑️")
        delete_btn.setFont(QtGui.QFont("Times New Roman", 12))
        delete_btn.setAttribute(Qt.WidgetAttribute.WA_NoMousePropagation, True)
        _ = delete_btn.clicked.connect(self._confirm_delete)
        delete_btn.setFixedWidth(30)
        delete_btn.setStyleSheet("background-color: #515151")
        delete_btn.setToolTip("Delete page")

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(btn_below)
        btn_row.addWidget(change_date_btn)
        btn_row.addWidget(delete_btn)
        btn_row.addStretch()

        # Main layout
        main_layout = QtWidgets.QGridLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self._graphics_view, 0, 0)

        # Create an overlay layout for the title and button
        overlay_layout = QtWidgets.QVBoxLayout()
        overlay_layout.addWidget(self.title_label)
        overlay_layout.addStretch()
        overlay_layout.addLayout(btn_row)
        overlay_layout.setContentsMargins(0, 10, 0, 10)

        # Add the overlay layout to the same grid cell (0, 0)
        main_layout.addLayout(overlay_layout, 0, 0)
        change_date_btn.raise_()
        delete_btn.raise_()

    def handle_drawing_input(
        self,
        position: QPointF,
        pressure: float = 1.0,
        action: InputAction = InputAction.PRESS,
        device: InputType = InputType.MOUSE,
        is_eraser: bool = False,
    ) -> None:
        """Handle drawing input from mouse, tablet, or touch"""
        # Use device-specific tool
        if device == InputType.MOUSE:
            current_tool = settings.MOUSE_TOOL
        else:  # TABLET or TOUCH
            current_tool = settings.TABLET_TOOL

        if current_tool == Tool.PEN and not is_eraser:
            self._handle_pen_input(position, pressure, action, device)
        elif current_tool == Tool.TEXT:
            self._handle_text_input(position, action)
        elif current_tool == Tool.ERASER or is_eraser:
            self._handle_eraser_input(position, action)
        elif current_tool == Tool.IMAGE:
            self._handle_image_input(position, action)
        elif current_tool == Tool.VIDEO:
            self._handle_video_input(position, action)

    def _handle_pen_input(
        self, position: QPointF, pressure: float, action: InputAction, device: InputType
    ) -> None:
        """Handle pen/drawing input"""
        if not settings.USE_PRESSURE:
            pressure = 1.0
        match action:
            case InputAction.PRESS:
                self._start_new_stroke(position, pressure, device)
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

            text_element = self._scene.create_text_element(
                text="",
                position=point,
                color=settings.CURRENT_COLOR,
                size_px=settings.TEXT_SIZE_PX,
            )
            if text_element:
                self.bottom_toolbar.selection_btn.click()
                text_element.start_editing()

            if text_element:
                self._logger.debug("Created text element at %s", scene_pos)

    def _handle_eraser_input(self, position: QPointF, action: InputAction) -> None:
        """Handle eraser input"""
        if action == InputAction.PRESS:
            self._is_erasing = True
            self._last_cursor = self.cursor()
            QtWidgets.QApplication.setOverrideCursor(Qt.CursorShape.BlankCursor)
        elif action == InputAction.MOVE and self._is_erasing:
            # Find and remove elements at position
            try:
                scene_pos = self._graphics_view.mapToScene(position.toPoint())
                elements = self._scene.get_elements_at_point(scene_pos)

                for element in elements:
                    if isinstance(element, (Stroke, Text)):
                        _ = self._scene.remove_element(element.element_id)
                        self._logger.debug("Erased element %s", element.element_id)
            except Exception as e:
                self._logger.error("Error during eraser operation: %s", e)
        else:
            self._is_erasing = False
            QtWidgets.QApplication.setOverrideCursor(self._last_cursor)

    def _start_new_stroke(
        self, position: QPointF, pressure: float, device: InputType
    ) -> None:
        """Start a new stroke"""
        scene_pos = self._graphics_view.mapToScene(position.toPoint())
        point = Point(scene_pos.x(), scene_pos.y(), pressure)

        # Get current drawing settings
        color = QtGui.QColor(settings.CURRENT_COLOR)
        thickness = settings.CURRENT_WIDTH

        # Create new stroke
        self._current_stroke = Stroke(
            points=[point], color=color.name(), size=thickness, tool="pen"
        )
        self._logger.info(
            "Created stroke with parameters: %s %s %s", point, color.name(), thickness
        )

        # Add to scene and get graphics item
        graphics_item = self._scene.add_element(self._current_stroke)

        if isinstance(graphics_item, StrokeGraphicsItem):
            self._current_stroke_item = graphics_item

        self._is_drawing = True
        self._points_since_smooth = 0
        self._current_points = []
        self._smoothed_points = []
        self._logger.debug("Started new stroke at %s", scene_pos)
        if device == InputType.TABLET:
            self._last_cursor = self.cursor()
            QtWidgets.QApplication.setOverrideCursor(Qt.CursorShape.BlankCursor)

        if point.y > settings.PAGE_HEIGHT / 10 * 8:
            self.add_below_dynamic.emit()

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

        self._current_points.append(point)
        self._points_since_smooth += 1

        if (
            settings.SMOOTHING_ENABLED
            and self._points_since_smooth >= 4
            and len(self._current_points) > 6
        ):
            # Get the last 7 points for smoothing
            window_start = max(0, len(self._smoothed_points) - 3)
            # Last 3 smoothed points + last 4 current points
            window_points = (
                self._smoothed_points[window_start:] + self._current_points[-4:]
            )

            newly_smoothed = smooth_stroke_advanced(window_points)

            # Only add the new smoothed points
            if len(self._smoothed_points) > 0:
                self._smoothed_points = (
                    self._smoothed_points[:window_start] + newly_smoothed
                )
            else:
                self._smoothed_points = newly_smoothed

            self._current_stroke_item.set_points(self._smoothed_points)
            self._points_since_smooth = 0
            self._current_points = []
        else:
            # Always show the stroke, even if not smoothing yet
            # Display smoothed points + current raw points
            display_points = self._smoothed_points + self._current_points
            self._current_stroke_item.set_points(display_points)

    def _finish_current_stroke(self, device: InputType) -> None:
        """Finish the current stroke"""
        _ = device  # Mark parameter as used to avoid warnings
        if self._current_stroke and self._current_stroke_item:
            # Get all points (smoothed + remaining current)
            final_points = self._smoothed_points + self._current_points

            # Apply beautification - try to recognize and beautify shapes
            if len(final_points) > 0:
                beautified_points, shape_name = beautify_stroke(final_points)

                if shape_name:
                    self._logger.info("Recognized shape: %s", shape_name)

                # Update the stroke with beautified points
                self._current_stroke_item.set_points(beautified_points)

            self._logger.debug(
                "Finished stroke with %s points", len(self._current_stroke.points)
            )
            self._scene.force_background_redraw()

            self._current_stroke = None
            self._current_stroke_item = None
            self._is_drawing = False
        QtWidgets.QApplication.setOverrideCursor(self._last_cursor)


    def handle_tablet_event(self, event: QtGui.QTabletEvent, position: QPointF) -> bool:
        """Handle tablet (pen) events"""
        pressure = event.pressure() if event.pressure() > 0 else 1.0

        if event.type() == QEvent.Type.TabletPress:
            action = InputAction.PRESS
        elif event.type() == QEvent.Type.TabletMove:
            action = InputAction.MOVE
        elif event.type() == QEvent.Type.TabletRelease:
            action = InputAction.RELEASE
        else:
            return False

        self.handle_drawing_input(
            position,
            pressure=pressure,
            action=action,
            device=InputType.TABLET,
            is_eraser=event.pointerType() == QtGui.QPointingDevice.PointerType.Eraser,
        )
        return True

    def handle_mouse_event(self, event: QtGui.QMouseEvent, position: QPointF) -> bool:
        """Handle mouse events"""
        action = InputAction.PRESS
        if event.type() == QtGui.QMouseEvent.Type.MouseMove:
            action = InputAction.MOVE
        elif event.type() == QtGui.QMouseEvent.Type.MouseButtonRelease:
            action = InputAction.RELEASE

        if event.buttons() & Qt.MouseButton.LeftButton or action == InputAction.RELEASE:
            self.handle_drawing_input(position, pressure=1.0, action=action)
            return True

        return False

    def _handle_image_input(self, position: QPointF, action: InputAction):
        """Handle input with Image tool"""
        if action == InputAction.PRESS:
            scene_pos = self._graphics_view.mapToScene(position.toPoint())
            point = Point(scene_pos.x(), scene_pos.y(), 1.0)

            image_file, _ = QtWidgets.QFileDialog.getOpenFileName(
                self.parentWidget(),
                "Select image",
                filter=("Images (*.png *.xpm *.jpg *.jpeg *.webp)"),
            )
            self._logger.debug("Selected image: %s", image_file)
            if not image_file:
                return
            (image_bytes, height, width) = read_image(image_file)
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

    def _handle_video_input(self, position: QPointF, action: InputAction) -> None:
        """Handle input with Video tool"""
        if action != InputAction.PRESS:
            return

        scene_pos = self._graphics_view.mapToScene(position.toPoint())
        point = Point(scene_pos.x(), scene_pos.y(), 1.0)

        video_file, _ = QtWidgets.QFileDialog.getOpenFileName(
            self.parentWidget(),
            "Select video",
            filter=("Videos (*.mp4 *.mov *.webm *.mkv *.avi)"),
        )
        self._logger.debug("Selected video: %s", video_file)
        if not video_file:
            return

        try:
            with open(video_file, "rb") as handle:
                video_bytes = handle.read()
        except (OSError, IOError) as exc:
            _ = show_error_dialog(self, "Failed to load video", str(exc))
            return

        # Default to a smaller on-canvas size to keep videos manageable.
        default_width = 320.0
        default_height = 180.0

        thumbnail_bytes = generate_video_thumbnail(video_file)

        video = Video(
            position=point,
            width=default_width,
            height=default_height,
            rotation=0.0,
            video_data=video_bytes,
            thumbnail_data=thumbnail_bytes,
        )
        _ = self._scene.add_element(video)

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

    @override
    def keyPressEvent(self, a0: QtGui.QKeyEvent | None) -> None:
        """On key pressed (delete element)"""
        event = a0
        if event and event.key() == Qt.Key.Key_Delete:
            selected_elements = self.get_selected_elements()
            self._logger.info("Deleting elements %s", selected_elements)
            for element in selected_elements:
                _ = self._scene.remove_element(element.element_id)
        return super().keyPressEvent(event)

    def change_date(self):
        """Change date for the page; opens a dialog to ask for it"""
        new_date_str, result = QtWidgets.QInputDialog.getText(
            self.parentWidget(), "New date", "Format: 01/01/2025"
        )
        if not result:
            return
        fields = new_date_str.split("/")
        if len(fields) != 3:
            _ = show_error_dialog(self.parentWidget(), "Error", "Wrong format")
            return

        try:
            new_date = datetime.strptime(
                f"{fields[0]}/{fields[1]}/{fields[2]}", "%d/%m/%Y"
            )
            self.page.created_at = new_date.timestamp()
            self.page_modified.emit()
            self.date_changed.emit(self.page_index)  # Trigger streak recalculation
            self._update_title_label()
        except ValueError as e:
            _ = show_error_dialog(self.parentWidget(), "Error", "Wrong format")
            self._logger.error(e)

    def _update_title_label(self) -> None:
        """Update the title label with current page info"""
        page_date = datetime.fromtimestamp(
            self.page.created_at if self.page else 0
        ).strftime("%Y-%m-%d %a")
        streak_info = ""
        if self.page and self.page.streak_lvl > 0:
            streak_info = f" (Streak: {self.page.streak_lvl})"
        self.title_label.setText(f"{page_date}{streak_info}")

    def _confirm_delete(self):
        result = confirm_delete(self.parentWidget())
        if result:
            self.delete_page.emit(self.page_index)
