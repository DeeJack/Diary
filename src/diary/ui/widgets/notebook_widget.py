"""The widget for the Notebook containing the PageWidgets"""

import logging
from typing import Literal, cast, override

from PyQt6 import QtCore, QtGui, QtWidgets

from diary.config import settings
from diary.models import Notebook, Page
from diary.ui.graphics_items.page_graphics_widget import PageGraphicsWidget
from diary.ui.graphics_items.text_graphics_item import TextGraphicsItem
from diary.ui.input import InputType
from diary.ui.ui_utils import show_info_dialog
from diary.ui.widgets.bottom_toolbar import BottomToolbar
from diary.ui.widgets.save_manager import SaveManager
from diary.ui.widgets.tool_selector import Tool
from diary.utils.encryption import SecureBuffer


class NotebookWidget(QtWidgets.QGraphicsView):
    """The widget for the Notebook containing the PageWidgets"""

    current_page_changed: QtCore.pyqtSignal = QtCore.pyqtSignal(
        int, int
    )  # current_page_index, total_pages
    current_zoom: float = 1.0
    min_zoom: float = 0.6
    max_zoom: float = 1.7
    page_height: int = settings.PAGE_HEIGHT + settings.PAGE_BETWEEN_SPACING
    _initial_load_complete: bool = False

    def __init__(
        self,
        key_buffer: SecureBuffer,
        salt: bytes,
        notebook: Notebook,
        all_notebooks: list[Notebook],
        bottom_toolbar: BottomToolbar,
    ):
        super().__init__()
        self.notebook: Notebook = notebook or Notebook([Page(), Page()])
        self._logger: logging.Logger = logging.getLogger("NotebookWidget")
        # { page_index: QGraphicsProxyWidget, ... }
        self.active_page_widgets: dict[int, QtWidgets.QGraphicsProxyWidget] = {}
        # Dictionary to hold background rectangles for all pages (always visible)
        self.page_backgrounds: dict[int, QtWidgets.QGraphicsRectItem] = {}
        self.bottom_toolbar: BottomToolbar = bottom_toolbar

        # Initialize save manager
        self.save_manager: SaveManager = SaveManager(
            all_notebooks,
            settings.NOTEBOOK_FILE_PATH,
            key_buffer,
            salt,
        )
        self.this_scene: QtWidgets.QGraphicsScene = QtWidgets.QGraphicsScene()
        self._cleaning_up: bool = False

        self._setup_notebook_widget()
        self._layout_page_backgrounds()
        self._on_scroll()  # Initial load

    def cleanup(self) -> None:
        """Clean up all resources before application close to prevent segfaults.

        This method should be called from the main window's closeEvent before
        Qt starts destroying objects, to ensure proper cleanup order.
        """
        self._cleaning_up = True
        self._logger.debug("Cleaning up NotebookWidget")

        # Stop the auto-save timer first
        self.save_manager.stop_auto_save()

        # Disconnect scroll handler to prevent callbacks during cleanup
        scroll_bar = self.verticalScrollBar()
        if scroll_bar:
            try:
                scroll_bar.valueChanged.disconnect(self._on_scroll)
            except (TypeError, RuntimeError):
                pass

        # Clean up all active page widgets
        for page_index, proxy_widget in list(self.active_page_widgets.items()):
            self._cleanup_proxy_widget(proxy_widget, page_index)
        self.active_page_widgets.clear()

        # Clear page backgrounds
        for background in self.page_backgrounds.values():
            try:
                self.this_scene.removeItem(background)
            except RuntimeError:
                pass
        self.page_backgrounds.clear()

        # Clear the scene
        self.this_scene.clear()

        self._logger.debug("NotebookWidget cleanup complete")

    def _setup_notebook_widget(self):
        """Init configurations for the widget"""
        self.setScene(self.this_scene)
        # Accept events, handle dragging...
        current_viewport = self.viewport()
        assert current_viewport is not None
        current_viewport.setAttribute(QtCore.Qt.WidgetAttribute.WA_AcceptTouchEvents)
        current_viewport.setAttribute(QtCore.Qt.WidgetAttribute.WA_TabletTracking, True)
        current_viewport.installEventFilter(self)
        current_viewport.grabGesture(
            QtCore.Qt.GestureType.PinchGesture,
            QtCore.Qt.GestureFlag.ReceivePartialGestures,
        )

        self.setRenderHints(self.renderHints())
        self.select_tool(Tool.PEN, "mouse")

        scroll_bar = self.verticalScrollBar()
        if scroll_bar:
            _ = scroll_bar.valueChanged.connect(self._on_scroll)

    def _layout_page_backgrounds(self):
        """Set up scene rect - backgrounds are created lazily on scroll"""
        self.page_backgrounds.clear()
        self._update_scene_rect()

    def _on_scroll(self, value: int = 0) -> None:
        """Handle scroll events to lazy load pages and backgrounds"""
        _ = value
        if self._cleaning_up:
            return
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
                self._cleanup_proxy_widget(proxy_widget, page_index)

        # Unload backgrounds outside the buffer range
        backgrounds_to_unload = set(self.page_backgrounds.keys()) - pages_to_load
        for page_index in backgrounds_to_unload:
            background = self.page_backgrounds.pop(page_index, None)
            if background:
                try:
                    self.this_scene.removeItem(background)
                except RuntimeError:
                    pass

        # Load new backgrounds and widgets
        for page_index in pages_to_load:
            # Create background if not exists
            if page_index not in self.page_backgrounds:
                self._create_page_background(page_index)
            # Create widget if not exists
            if page_index not in self.active_page_widgets:
                page_data = self.notebook.pages[page_index]
                self._load_and_position_page(page_index, page_data)
        # Update current page indicator
        self.update_navbar()

    def _add_page_to_scene(
        self, page_data: Page, page_index: int
    ) -> QtWidgets.QGraphicsProxyWidget | None:
        # Create the page widget
        page_widget = PageGraphicsWidget(page_data, page_index, self.bottom_toolbar)

        _ = page_widget.add_below_dynamic.connect(
            lambda idx=page_index: self._add_page_below_dynamic(idx)
        )
        _ = page_widget.delete_page.connect(self._delete_page)
        _ = page_widget.page_modified.connect(self.save_manager.mark_dirty)
        _ = page_widget.add_below.connect(self.add_page_below)
        _ = page_widget.date_changed.connect(self._on_page_date_changed)

        # Add to scene as proxy widget
        try:
            proxy_widget = self.this_scene.addWidget(page_widget)
        except RuntimeError:
            return None  # Object has been deleted (when closing)
        return proxy_widget

    def _cleanup_proxy_widget(
        self, proxy_widget: QtWidgets.QGraphicsProxyWidget, page_index: int
    ) -> None:
        """Clean up a proxy widget and its underlying page widget to prevent memory leaks.

        This method properly disconnects signals, clears scene items, and schedules
        deletion of both the page widget and proxy widget.
        """
        try:
            # Get the underlying page widget
            page_widget = proxy_widget.widget()

            # Remove from scene first
            self.this_scene.removeItem(proxy_widget)

            if page_widget and isinstance(page_widget, PageGraphicsWidget):
                # Disconnect signals from the page widget to prevent callbacks
                try:
                    page_widget.add_below_dynamic.disconnect()
                    page_widget.delete_page.disconnect()
                    page_widget.page_modified.disconnect()
                    page_widget.add_below.disconnect()
                    page_widget.date_changed.disconnect()
                except (TypeError, RuntimeError):
                    pass  # Signals may already be disconnected

                # Call cleanup to clear internal resources
                page_widget.cleanup()

                # Schedule the widget for deletion
                page_widget.deleteLater()

            # Schedule the proxy widget for deletion
            proxy_widget.deleteLater()

            self._logger.debug("Unloaded and cleaned up page %s", page_index)
        except RuntimeError:
            pass  # Object has been destroyed (when closing)

    def _on_page_date_changed(self, page_index: int) -> None:
        """Handle date change on a page by recalculating streak levels"""
        self.notebook.update_page_streak(page_index)
        self._logger.debug(
            "Updated streak levels after date change on page %d", page_index
        )
        # Update title labels for affected pages
        self._update_page_title_labels(page_index)
        self.save_manager.mark_dirty()

    def _update_page_title_labels(self, from_index: int) -> None:
        """Update title labels for pages from the given index onwards"""
        for idx in range(from_index, len(self.notebook.pages)):
            if idx in self.active_page_widgets:
                proxy = self.active_page_widgets[idx]
                widget = proxy.widget()
                if widget and isinstance(widget, PageGraphicsWidget):
                    widget._update_title_label()  # pyright: ignore[reportPrivateUsage]

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
            return None
        if (
            event.key() == QtCore.Qt.Key.Key_Q
            and event.modifiers() == QtCore.Qt.KeyboardModifier.ControlModifier
        ):
            self._logger.debug("Pressed 'CTRL + Q', closing...")
            QtWidgets.QApplication.closeAllWindows()
            return None
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
        if page_idx == len(self.notebook.pages) - 1 and settings.DYNAMIC_ADD_PAGES:
            self.add_page_below(page_idx)

    def _delete_page(self, page_idx: int) -> None:
        """Delete a page at the specified index"""
        self._logger.debug("Deleting page %s", page_idx)
        # Prevent deletion if it's the only page
        if len(self.notebook.pages) <= 1:
            _ = show_info_dialog(
                self, "Cannot delete page", "Cannot delete last remaining page"
            )
            return

        # Remove page from notebook
        if not self.notebook.remove_page(page_idx):
            return

        # Remove page widget from scene with proper cleanup
        if page_idx in self.active_page_widgets:
            proxy_widget = self.active_page_widgets.pop(page_idx)
            self._cleanup_proxy_widget(proxy_widget, page_idx)

        # Remove page background
        if page_idx in self.page_backgrounds:
            background = self.page_backgrounds[page_idx]
            self.this_scene.removeItem(background)
            del self.page_backgrounds[page_idx]

        self._update_pages_after_deletion(page_idx)

    def add_page_below(self, page_idx: int):
        """Adds a page below the provided index"""
        self._logger.debug("Adding page below %s", page_idx)
        new_page = Page()
        self.notebook.add_page(new_page, page_idx + 1)
        new_page_idx = page_idx + 1

        # update all widgets by shifting them down
        self._reindex_pages(page_idx, direction=1)

        # Now add the new page's background at the correct position
        self._create_page_background(new_page_idx)
        self._update_scene_rect()

        # Load the new page if it's in the visible range
        self._load_and_position_page(new_page_idx, new_page)

        self.save_manager.mark_dirty()
        self.update_navbar()

    def _update_pages_after_deletion(self, page_idx: int):
        """Update indices and positions for pages after a deletion."""
        self._reindex_pages(page_idx, direction=-1)

        self._update_scene_rect()

        self.save_manager.mark_dirty()
        self.update_navbar()

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

    def select_tool(self, new_tool: Tool, device: str = "tablet"):
        """Selects a new tool for a specific device, changing the cursor and drag mode"""
        if device == "mouse":
            settings.MOUSE_TOOL = new_tool
        else:  # tablet/pen
            settings.TABLET_TOOL = new_tool

        if not settings.MOUSE_ENABLED or new_tool == Tool.DRAG:
            self.setDragMode(self.DragMode.ScrollHandDrag)
        else:
            self.setDragMode(self.DragMode.NoDrag)

        # If the tool is Selection, set all the items to be selectable/movable
        # Otherwise, unset the flag
        for page in self.this_scene.items():
            if isinstance(page, QtWidgets.QGraphicsProxyWidget) and isinstance(
                page.widget(), PageGraphicsWidget
            ):
                page_widget = cast(PageGraphicsWidget, page.widget())
                for element in page_widget.scene.items():
                    element.setFlag(
                        QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsMovable,
                        new_tool == Tool.SELECTION,
                    )
                    element.setFlag(
                        QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsSelectable,
                        new_tool == Tool.SELECTION,
                    )
                    if new_tool == Tool.SELECTION and isinstance(
                        element, TextGraphicsItem
                    ):
                        element.stop_editing()

        self._logger.debug("Setting new tool: %s for device: %s", new_tool, device)

    def change_color(self, new_color: QtGui.QColor):
        """Change the color for the pen"""
        settings.CURRENT_COLOR = new_color.name()
        self._logger.debug("Setting new color: %s", new_color)

    def change_thickness(self, new_thickness: float):
        """Change the thickness for the pen"""
        settings.CURRENT_WIDTH = new_thickness
        self._logger.debug("Setting new thickness: %s", new_thickness)

    def reload(self) -> None:
        """Reload the notebook from file, refreshing all content"""
        self._logger.debug("Reloading notebook from file")

        # Clear all active widgets with proper cleanup
        for page_index, proxy_widget in list(self.active_page_widgets.items()):
            self._cleanup_proxy_widget(proxy_widget, page_index)
        self.active_page_widgets.clear()

        # Clear page backgrounds
        for background in self.page_backgrounds.values():
            try:
                self.this_scene.removeItem(background)
            except RuntimeError:
                pass  # Object may have been destroyed
        self.page_backgrounds.clear()

        # Re-layout page backgrounds for the reloaded notebook
        self._layout_page_backgrounds()

        # Trigger scroll handler to reload visible pages
        self._on_scroll()

        # Update navigation bar
        self.update_navbar()

        self._logger.debug("Notebook reload complete")

    @override
    def eventFilter(self, a0: QtCore.QObject | None, a1: QtCore.QEvent | None) -> bool:
        """Handle events for drawing and input across all pages"""
        obj, event = a0, a1
        if obj != self.viewport() or event is None or obj is None:
            return super().eventFilter(obj, event)

        # Skip events for drag and selection tools based on input device
        if isinstance(event, QtGui.QTabletEvent):
            active_tool = settings.TABLET_TOOL
            device = InputType.TABLET
        else:  # Mouse event
            active_tool = settings.MOUSE_TOOL
            device = InputType.MOUSE

        if active_tool in {Tool.DRAG, Tool.SELECTION} or (
            not settings.MOUSE_ENABLED and device == InputType.MOUSE
        ):
            self.setDragMode(self.DragMode.ScrollHandDrag)
            return super().eventFilter(obj, event)

        # Handle tablet events
        if isinstance(event, QtGui.QTabletEvent):
            return self._handle_tablet_event(event)

        # Handle mouse events for drawing
        if isinstance(event, QtGui.QMouseEvent) and settings.MOUSE_ENABLED:
            return self._handle_mouse_event(event)

        return super().eventFilter(obj, event)

    def _handle_tablet_event(self, event: QtGui.QTabletEvent) -> bool:
        """Handle tablet events and route to correct page"""
        # Convert position to QPoint for mapToScene
        if (
            settings.TABLET_TOOL != Tool.DRAG
            and self.dragMode() != self.DragMode.NoDrag
        ):
            self.setDragMode(self.DragMode.NoDrag)
        point = QtCore.QPoint(int(event.position().x()), int(event.position().y()))
        scene_pos = self.mapToScene(point)

        # Find which page this event belongs to
        page_index = int(scene_pos.y() / self.page_height)

        if page_index in self.active_page_widgets:
            proxy_widget = self.active_page_widgets[page_index]
            page_widget = proxy_widget.widget()

            if isinstance(page_widget, PageGraphicsWidget):
                # Convert to page-local coordinates
                page_local_pos = scene_pos - proxy_widget.pos()
                _ = page_widget.handle_tablet_event(event, page_local_pos)
                self.save_manager.mark_dirty()
                return True

        return False

    def _handle_mouse_event(self, event: QtGui.QMouseEvent) -> bool:
        """Handle mouse events and route to correct page"""
        # Convert viewport position to scene coordinates
        pos: QtCore.QPoint = event.position().toPoint()
        scene_pos: QtCore.QPointF = self.mapToScene(pos)

        # Find which page this event belongs to
        page_index = int(scene_pos.y() / self.page_height)

        if page_index in self.active_page_widgets:
            proxy_widget = self.active_page_widgets[page_index]
            page_widget = proxy_widget.widget()

            if isinstance(page_widget, PageGraphicsWidget):
                # Convert to page-local coordinates
                page_local_pos = scene_pos - proxy_widget.pos()
                _ = page_widget.handle_mouse_event(event, page_local_pos)
                self.save_manager.mark_dirty()
                return True

        return False

    def _create_page_background(self, page_idx: int):
        """Create a page background for unloaded pages"""
        y_offset = page_idx * self.page_height

        # Create a light background rectangle
        background = QtWidgets.QGraphicsRectItem(
            0, y_offset, settings.PAGE_WIDTH, settings.PAGE_HEIGHT
        )
        background.setBrush(QtGui.QBrush(QtGui.QColor(settings.PAGE_BACKGROUND_COLOR)))

        try:
            self.this_scene.addItem(background)
        except RuntimeError:
            return  # Scene has been deleted (during close)
        self.page_backgrounds[page_idx] = background

    def _update_scene_rect(self):
        """Update the scene rect to fit all pages"""
        total_height = len(self.notebook.pages) * self.page_height
        self.this_scene.setSceneRect(0, 0, settings.PAGE_WIDTH, total_height)

    def _reindex_pages(self, start_idx: int, direction: Literal[1, -1]):
        """Reindex pages starting from start_idx in the given direction (1 for insertion, -1 for deletion)"""
        widgets_to_update: dict[int, QtWidgets.QGraphicsProxyWidget] = {}
        backgrounds_to_update: dict[int, QtWidgets.QGraphicsRectItem] = {}

        # Process in reverse order to avoid key conflicts during updates
        for idx in sorted(self.active_page_widgets.keys(), reverse=True):
            if idx > start_idx:
                # Move widget and background down (increment index)
                new_idx = idx + direction
                new_y_offset = new_idx * self.page_height

                # Update widget position and index
                widget = self.active_page_widgets[idx]
                widget.setPos(0, new_y_offset)
                cast(PageGraphicsWidget, widget.widget()).page_index = new_idx
                widgets_to_update[new_idx] = widget

        # Process backgrounds in reverse order
        for idx in sorted(self.page_backgrounds.keys(), reverse=True):
            if idx > start_idx:
                # Move background down (increment index)
                new_idx = idx + direction
                new_y_offset = new_idx * self.page_height

                background = self.page_backgrounds[idx]
                background.setPos(0, new_y_offset)
                backgrounds_to_update[new_idx] = background

        # Clear old indices and update with new ones
        for idx in list(self.active_page_widgets.keys()):
            if idx > start_idx:
                del self.active_page_widgets[idx]

        for idx in list(self.page_backgrounds.keys()):
            if idx > start_idx:
                del self.page_backgrounds[idx]

        self.active_page_widgets.update(widgets_to_update)
        self.page_backgrounds.update(backgrounds_to_update)

    def _load_and_position_page(self, new_page_idx: int, new_page_data: Page):
        """Load and position a page at the given index"""
        self._logger.debug("Loaded page %s", new_page_idx)

        y_offset = new_page_idx * self.page_height
        proxy_widget = self._add_page_to_scene(new_page_data, new_page_idx)
        if proxy_widget:
            proxy_widget.setPos(0, y_offset)
            self.active_page_widgets[new_page_idx] = proxy_widget
