"""The widget for the Notebook containing the PageWidgets"""

import logging
import sys
from pathlib import Path
from typing import cast, override

from PyQt6 import QtCore, QtGui, QtWidgets

from diary.config import SETTINGS_FILE_PATH, settings
from diary.models import Notebook, Page
from diary.ui.graphics_items.page_graphics_widget import PageGraphicsWidget
from diary.ui.widgets.save_manager import SaveManager
from diary.ui.widgets.tool_selector import Tool, get_cursor_from_tool
from diary.utils.encryption import SecureBuffer


class NotebookWidget(QtWidgets.QGraphicsView):
    """The widget for the Notebook containing the PageWidgets"""

    current_page_changed: QtCore.pyqtSignal = QtCore.pyqtSignal(
        int, int
    )  # current_page_index, total_pages
    current_zoom: float = 1.0
    min_zoom: float = 0.6
    max_zoom: float = 1.4
    page_height: int = settings.PAGE_HEIGHT + settings.PAGE_BETWEEN_SPACING
    _initial_load_complete: bool = False

    def __init__(
        self,
        key_buffer: SecureBuffer,
        salt: bytes,
        status_bar: QtWidgets.QStatusBar,
        notebook: Notebook | None = None,
    ):
        super().__init__()
        self.notebook: Notebook = notebook or Notebook([Page(), Page()])
        self._logger: logging.Logger = logging.getLogger("NotebookWidget")
        # { page_index: QGraphicsProxyWidget, ... }
        self.active_page_widgets: dict[int, QtWidgets.QGraphicsProxyWidget] = {}
        # Dictionary to hold background rectangles for all pages (always visible)
        self.page_backgrounds: dict[int, QtWidgets.QGraphicsRectItem] = {}

        # Initialize save manager
        self.save_manager: SaveManager = SaveManager(
            self.notebook,
            settings.NOTEBOOK_FILE_PATH,
            key_buffer,
            salt,
            status_bar,
        )
        self.this_scene: QtWidgets.QGraphicsScene = QtWidgets.QGraphicsScene()

        self._setup_notebook_widget()
        self._layout_page_backgrounds()
        self._on_scroll()  # Initial load

    def _setup_notebook_widget(self):
        """Init configurations for the widget"""
        self.setScene(self.this_scene)
        # Accept events, handle dragging...
        current_viewport = self.viewport()
        assert current_viewport is not None
        current_viewport.setAttribute(QtCore.Qt.WidgetAttribute.WA_AcceptTouchEvents)
        current_viewport.grabGesture(
            QtCore.Qt.GestureType.PinchGesture,
            QtCore.Qt.GestureFlag.ReceivePartialGestures,
        )

        self.setRenderHints(self.renderHints())
        self.select_tool(Tool.PEN)

        scroll_bar = self.verticalScrollBar()
        if scroll_bar:
            _ = scroll_bar.valueChanged.connect(self._on_scroll)

    def _layout_page_backgrounds(self):
        """Draw page backgrounds for all pages as placeholders"""
        self.page_backgrounds.clear()

        for i, _ in enumerate(self.notebook.pages):
            y_offset = i * self.page_height

            # Create a light background rectangle
            background = QtWidgets.QGraphicsRectItem(
                0, y_offset, settings.PAGE_WIDTH, settings.PAGE_HEIGHT
            )
            background.setBrush(
                QtGui.QBrush(QtGui.QColor(settings.PAGE_BACKGROUND_COLOR))
            )
            # background.setPen(QColor(settings.PAGE_BACKGROUND_COLOR))

            self.this_scene.addItem(background)
            self.page_backgrounds[i] = background

        # Set scene rect to contain all pages
        total_height = len(self.notebook.pages) * self.page_height
        self.this_scene.setSceneRect(0, 0, settings.PAGE_WIDTH, total_height)

    def _on_scroll(self, value: int = 0) -> None:
        """Handle scroll events to lazy load pages"""
        _ = value
        # Determine which pages should be visible
        viewport = self.viewport()
        if not viewport:
            return
        visible_rect = self.mapToScene(viewport.rect()).boundingRect()
        first_visible_page = max(0, int(visible_rect.top() / self.page_height))
        last_visible_page = min(
            len(self.notebook.pages) - 1, int(visible_rect.bottom() / self.page_height)
        )

        # Add buffer pages above and below for smoother scrolling
        buffer_pages = 6
        first_visible_page = max(0, first_visible_page - buffer_pages)
        last_visible_page = min(
            len(self.notebook.pages) - 1, last_visible_page + buffer_pages
        )

        # Determine pages to load and unload
        pages_to_load = set(range(first_visible_page, last_visible_page + 1))
        pages_to_unload = set(self.active_page_widgets.keys()) - pages_to_load

        # Unload old widgets
        for page_index in pages_to_unload:
            proxy_widget = self.active_page_widgets.pop(page_index, None)
            if proxy_widget:
                try:
                    self.this_scene.removeItem(proxy_widget)
                    self._logger.debug("Unloaded page %s", page_index)
                except RuntimeError:
                    pass  # Object has been destoryed (when closing)

        # Load new widgets
        for page_index in pages_to_load:
            if page_index not in self.active_page_widgets:
                page_data = self.notebook.pages[page_index]
                proxy_widget = self._add_page_to_scene(page_data, page_index)
                if not proxy_widget:
                    return

                # Calculate the y_offset for this page
                y_offset = page_index * self.page_height
                proxy_widget.setPos(0, y_offset)

                # Store the active widget
                self.active_page_widgets[page_index] = proxy_widget

                self._logger.debug(
                    "Loaded page %s at y_offset %s", page_index, y_offset
                )
        # Update current page indicator
        self.update_navbar()

    def _add_page_to_scene(
        self, page_data: Page, page_index: int
    ) -> QtWidgets.QGraphicsProxyWidget | None:
        # Create the page widget
        page_widget = PageGraphicsWidget(page_data, page_index)

        _ = page_widget.add_below_dynamic.connect(
            lambda idx=page_index: self._add_page_below_dynamic(idx)
        )
        _ = page_widget.page_modified.connect(self.save_manager.mark_dirty)

        # Add to scene as proxy widget
        try:
            proxy_widget = self.this_scene.addWidget(page_widget)
        except RuntimeError:
            return None  # Object has been deleted (when closing)
        return proxy_widget

    @override
    def viewportEvent(self, event: QtCore.QEvent | None):
        """Handles the Pinch gesture to zoom in/out"""
        if event is None or not isinstance(event, QtWidgets.QGestureEvent):
            return super().viewportEvent(event)

        if event.type() == QtCore.QEvent.Type.Gesture:
            pinch = event.gesture(QtCore.Qt.GestureType.PinchGesture)
            if (
                pinch
                and pinch.state() == QtCore.Qt.GestureState.GestureUpdated
                and isinstance(pinch, QtWidgets.QPinchGesture)
            ):
                # Scale view around center point
                self.setTransformationAnchor(
                    QtWidgets.QGraphicsView.ViewportAnchor.AnchorUnderMouse
                )

                scale_factor: float = self.current_zoom * pinch.scaleFactor()
                new_zoom = max(
                    self.min_zoom * 1.15, min(scale_factor, self.max_zoom * 1.15)
                )
                scale_factor = new_zoom / self.current_zoom
                self.scale(
                    scale_factor,
                    scale_factor,
                )
                self.current_zoom = new_zoom
                return True
        return super().viewportEvent(event)

    @override
    def wheelEvent(self, event: QtGui.QWheelEvent | None):
        """
        Zooms in/out on the current cursor position if CTRL is being pressed
        """
        if event is None:
            return
        if event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                new_zoom = self.current_zoom * 1.15
            else:
                new_zoom = self.current_zoom / 1.15
            new_zoom = max(self.min_zoom, min(self.max_zoom, new_zoom))
            zoom_factor = new_zoom / self.current_zoom

            self.scale(zoom_factor, zoom_factor)
            self.current_zoom = new_zoom
            # Prevent event from scrolling
            event.accept()
        else:
            super().wheelEvent(event)

    @override
    def keyPressEvent(self, event: QtGui.QKeyEvent | None) -> None:
        """Close app with 'Q'"""
        if not event:
            return super().keyPressEvent(event)
        if event.key() == QtCore.Qt.Key.Key_Q:
            self._logger.debug("Pressed 'Q', closing...")
            _ = self.close()
            sys.exit(0)
        return super().keyPressEvent(event)

    def save(self) -> None:
        """Save notebook synchronously"""
        self.save_manager.save()

    def save_async(self) -> None:
        """Save notebook asynchronously"""
        self.save_manager.save_async()

    def is_dirty(self) -> bool:
        """Check if notebook has unsaved changes"""
        return self.save_manager.is_dirty()

    def _add_page_below_dynamic(self, page_idx: int) -> None:
        """Add a page below if this is the last page"""
        if page_idx == len(self.notebook.pages) - 1:
            self.notebook.add_page()

            new_page_idx = len(self.notebook.pages) - 1
            new_page_data = self.notebook.pages[new_page_idx]

            # Add background
            y_offset = new_page_idx * self.page_height
            background = QtWidgets.QGraphicsRectItem(
                0, y_offset, settings.PAGE_WIDTH, settings.PAGE_HEIGHT
            )
            background.setBrush(
                QtGui.QBrush(QtGui.QColor(settings.PAGE_BACKGROUND_COLOR))
            )
            self.this_scene.addItem(background)
            self.page_backgrounds[new_page_idx] = background

            # Update scene rect to include the new page
            total_height = len(self.notebook.pages) * self.page_height
            self.this_scene.setSceneRect(0, 0, settings.PAGE_WIDTH, total_height)

            # Load the new page
            proxy_widget = self._add_page_to_scene(new_page_data, new_page_idx)
            if proxy_widget:
                # Position the new page
                proxy_widget.setPos(0, y_offset)
                self.active_page_widgets[new_page_idx] = proxy_widget

            self.save_manager.mark_dirty()
            self.update_navbar()

    @override
    def closeEvent(self, a0: QtGui.QCloseEvent | None):
        """Save notebook on close"""
        self._logger.debug("Close app event!")
        if a0 and self.notebook:
            settings.save_to_file(Path(SETTINGS_FILE_PATH))
            self.save_manager.force_save_on_close()

    def _get_current_page_index(self):
        """Estimate current page index based on viewport"""
        center_y = self.mapToScene(
            cast(QtWidgets.QWidget, self.viewport()).rect().center()
        ).y()
        page_height = settings.PAGE_HEIGHT + settings.PAGE_BETWEEN_SPACING
        return max(0, int(center_y / page_height))

    def scroll_to_page(self, page_index: int):
        """Scrolls to the selected page."""
        self._logger.debug("Scrolling to %s", page_index)
        if 0 <= page_index < len(self.notebook.pages):
            # Calculate the Y position of the target page
            y_pos = page_index * self.page_height
            scroll_bar = self.verticalScrollBar()
            if scroll_bar:
                scroll_bar.setValue(int(y_pos))

    def go_to_first_page(self) -> None:
        """Navigate to first page"""
        self.scroll_to_page(0)

    def go_to_last_page(self) -> None:
        """Navigate to last page"""
        if self.notebook.pages:
            self.scroll_to_page(len(self.notebook.pages) - 1)

    def update_navbar(self):
        """Update navigation bar with current page info"""
        current_page = self._get_current_page_index()
        total_pages = len(self.notebook.pages)
        self.current_page_changed.emit(current_page, total_pages)

    @override
    def showEvent(self, event: QtGui.QShowEvent | None) -> None:
        """Handle show event"""
        super().showEvent(event)
        if not self._initial_load_complete:
            self._initial_load_complete = True
            self.go_to_last_page()

    def select_tool(self, new_tool: Tool):
        """Selects a new tool, changing the cursor and drag mode"""
        settings.CURRENT_TOOL = new_tool
        self._logger.debug("Setting new tool: %s", new_tool)

        if new_tool != Tool.DRAG:
            self.setDragMode(QtWidgets.QGraphicsView.DragMode.NoDrag)
        else:
            self.setDragMode(QtWidgets.QGraphicsView.DragMode.ScrollHandDrag)
        QtWidgets.QApplication.setOverrideCursor(get_cursor_from_tool(new_tool))

    def change_color(self, new_color: QtGui.QColor):
        """Change the color for the pen"""
        settings.CURRENT_COLOR = new_color.name()
        self._logger.debug("Setting new color: %s", new_color)

    def change_thickness(self, new_thickness: float):
        """Change the thickness for the pen"""
        settings.CURRENT_WIDTH = new_thickness
        self._logger.debug("Setting new thickness: %s", new_thickness)
