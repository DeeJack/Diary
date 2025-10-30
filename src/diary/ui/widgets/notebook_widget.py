"""The widget for the Notebook containing the PageWidgets"""

import logging
import sys
from pathlib import Path
from typing import cast, override

from PyQt6.QtCore import (
    QEvent,
    QObject,
    QPoint,
    QPointF,
    Qt,
    QThread,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QBrush,
    QCloseEvent,
    QColor,
    QKeyEvent,
    QMouseEvent,
    QShowEvent,
    QTabletEvent,
    QTouchEvent,
    QWheelEvent,
)
from PyQt6.QtWidgets import (
    QApplication,
    QGestureEvent,
    QGraphicsProxyWidget,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QPinchGesture,
    QStatusBar,
    QWidget,
)

from diary.config import SETTINGS_FILE_PATH, settings
from diary.models import Notebook, NotebookDAO, Page
from diary.ui.graphics_items.page_graphics_widget import PageGraphicsWidget
from diary.ui.widgets.save_worker import SaveWorker
from diary.ui.widgets.tool_selector import Tool, get_cursor_from_tool
from diary.utils.backup import BackupManager
from diary.utils.encryption import SecureBuffer


class NotebookWidget(QGraphicsView):
    """The widget for the Notebook containing the PageWidgets"""

    current_page_changed: pyqtSignal = pyqtSignal(
        int, int
    )  # current_page_index, total_pages

    def __init__(
        self,
        key_buffer: SecureBuffer,
        salt: bytes,
        status_bar: QStatusBar,
        notebook: Notebook | None = None,
    ):
        super().__init__()
        self.current_zoom: float = 0.9
        self.min_zoom: float = 0.6
        self.max_zoom: float = 1.4
        self.notebook: Notebook = notebook or Notebook([Page(), Page()])

        self.pages_data: list[Page] = self.notebook.pages
        self.page_height: int = settings.PAGE_HEIGHT + settings.PAGE_BETWEEN_SPACING

        # { page_index: QGraphicsProxyWidget, ... }
        self.active_page_widgets: dict[int, QGraphicsProxyWidget] = {}

        # Dictionary to hold background rectangles for all pages (always visible)
        self.page_backgrounds: dict[int, QGraphicsRectItem] = {}

        self.key_buffer: SecureBuffer = key_buffer
        self.salt: bytes = salt
        self.backup_manager: BackupManager = BackupManager()
        self.logger: logging.Logger = logging.getLogger("NotebookWidget")
        self.is_saving: bool = False
        self.save_thread: QThread = QThread()
        self.save_worker: SaveWorker = SaveWorker(
            self.notebook,
            settings.NOTEBOOK_FILE_PATH,
            self.key_buffer,
            self.salt,
            status_bar,
        )
        self.status_bar: QStatusBar = status_bar
        self.this_scene: QGraphicsScene = QGraphicsScene()
        self.is_notebook_dirty: bool = False
        self._initial_load_complete: bool = False

        self._setup_notebook_widget()
        self._layout_page_backgrounds()
        self._on_scroll()  # Initial load

    def _setup_notebook_widget(self):
        """Init configurations for the widget"""
        self.setScene(self.this_scene)
        # Accept events, handle dragging...
        current_viewport = self.viewport()
        assert current_viewport is not None
        current_viewport.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents)
        current_viewport.grabGesture(
            Qt.GestureType.PinchGesture, Qt.GestureFlag.ReceivePartialGestures
        )
        current_viewport.installEventFilter(self)

        self.setRenderHints(self.renderHints())
        self.select_tool(Tool.PEN)

        scroll_bar = self.verticalScrollBar()
        if scroll_bar:
            _ = scroll_bar.valueChanged.connect(self._on_scroll)

        # Setup save timer
        timer = QTimer(self)
        timer.setInterval(1000 * settings.AUTOSAVE_NOTEBOOK_TIMEOUT)
        _ = timer.timeout.connect(self.save_async)
        timer.start()

    def _layout_page_backgrounds(self):
        """Draw page backgrounds for all pages as placeholders"""
        self.page_backgrounds.clear()

        for i, _ in enumerate(self.pages_data):
            y_offset = i * self.page_height

            # Create a light background rectangle
            background = QGraphicsRectItem(
                0, y_offset, settings.PAGE_WIDTH, settings.PAGE_HEIGHT
            )
            background.setBrush(QBrush(QColor(245, 245, 245)))  # Light gray background
            background.setPen(QColor(200, 200, 200))  # Light border

            self.this_scene.addItem(background)
            self.page_backgrounds[i] = background

        # Set scene rect to contain all pages
        total_height = len(self.pages_data) * self.page_height
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
            len(self.pages_data) - 1, int(visible_rect.bottom() / self.page_height)
        )

        # Add buffer pages above and below for smoother scrolling
        buffer_pages = 6
        first_visible_page = max(0, first_visible_page - buffer_pages)
        last_visible_page = min(
            len(self.pages_data) - 1, last_visible_page + buffer_pages
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
                    self.logger.debug("Unloaded page %s", page_index)
                except RuntimeError:
                    pass  # Object has been destoryed (when closing)

        # Load new widgets
        for page_index in pages_to_load:
            if page_index not in self.active_page_widgets:
                page_data = self.pages_data[page_index]
                proxy_widget = self._add_page_to_scene(page_data, page_index)
                assert proxy_widget is not None

                # Calculate the y_offset for this page
                y_offset = page_index * self.page_height
                proxy_widget.setPos(0, y_offset)

                # Store the active widget
                self.active_page_widgets[page_index] = proxy_widget

                self.logger.debug("Loaded page %s at y_offset %s", page_index, y_offset)
        # Update current page indicator
        self.update_navbar()

    def _add_page_to_scene(
        self, page_data: Page, page_index: int
    ) -> QGraphicsProxyWidget | None:
        # Create the page widget
        page_widget = PageGraphicsWidget(page_data, page_index)

        # Connect page widget signals
        _ = page_widget.add_below.connect(
            lambda _, idx=page_index: self._add_page_below(self.pages_data[idx])
        )
        _ = page_widget.add_below_dynamic.connect(
            lambda _, idx=page_index: self._add_page_below_dynamic(self.pages_data[idx])
        )
        _ = page_widget.page_modified.connect(
            lambda: setattr(self, "is_notebook_dirty", True)
        )

        # Add to scene as proxy widget
        try:
            proxy_widget = self.this_scene.addWidget(page_widget)
        except RuntimeError:
            return None  # Object has been deleted (when closing)
        return proxy_widget

    @override
    def viewportEvent(self, event: QEvent | None):
        """Handles the Pinch gesture to zoom in/out"""
        if event is None or not isinstance(event, QGestureEvent):
            return super().viewportEvent(event)

        if event.type() == QEvent.Type.Gesture:
            pinch = event.gesture(Qt.GestureType.PinchGesture)
            if (
                pinch
                and pinch.state() == Qt.GestureState.GestureUpdated
                and isinstance(pinch, QPinchGesture)
            ):
                # Scale view around center point
                self.setTransformationAnchor(
                    QGraphicsView.ViewportAnchor.AnchorUnderMouse
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
    def wheelEvent(self, event: QWheelEvent | None):
        """
        Zooms in/out on the current cursor position if CTRL is being pressed
        """
        if event is None:
            return
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
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
    def eventFilter(self, obj: QObject | None, event: QEvent | None) -> bool:  # pyright: ignore[reportIncompatibleMethodOverride]
        """Intercepts events to forward Tablet and Mouse Events to the PageWidget"""
        if obj != self.viewport() or event is None or obj is None:
            return super().eventFilter(obj, event)

        if settings.CURRENT_TOOL in {Tool.DRAG, Tool.SELECTION}:
            return super().eventFilter(obj, event)

        # Handle tablet events
        if isinstance(event, QTabletEvent):
            return self._handle_tablet_event(event)

        # Handle mouse events for drawing
        if isinstance(event, QMouseEvent) and settings.MOUSE_ENABLED:
            return self._handle_mouse_event(event)

        # Handle touch events for drawing
        if isinstance(event, QTouchEvent) and settings.TOUCH_ENABLED:
            return self._handle_touch_event(event)

        return super().eventFilter(obj, event)

    def _handle_tablet_event(self, event: QTabletEvent) -> bool:
        """Handle tablet events and forward to appropriate page widget"""
        # Get position in viewport
        pos: QPoint = event.position().toPoint()
        scene_pos: QPointF = self.mapToScene(pos)

        # Find page at position
        scene = self.scene()
        if scene is None:
            return False
        # Convert position to QPoint for mapToScene
        point = QPoint(int(event.position().x()), int(event.position().y()))
        scene_pos = self.mapToScene(point)

        # Find which page this event belongs to
        page_index = int(scene_pos.y() / self.page_height)

        if page_index in self.active_page_widgets:
            proxy_widget = self.active_page_widgets[page_index]
            page_widget = proxy_widget.widget()

            if isinstance(page_widget, PageGraphicsWidget):
                # Convert to page-local coordinates
                page_local_pos = scene_pos - proxy_widget.pos()
                page_widget.handle_tablet_event(event, page_local_pos)
                self.is_notebook_dirty = True
                return True

        return False

    def _handle_mouse_event(self, event: QEvent) -> bool:
        """Handle mouse events and forward to appropriate page widget"""
        if not isinstance(event, QMouseEvent):
            return False
        pos = event.position() if hasattr(event, "position") else event.pos()
        point = QPoint(int(pos.x()), int(pos.y()))
        scene_pos = self.mapToScene(point)

        # Find which page this event belongs to
        page_index = int(scene_pos.y() / self.page_height)

        if page_index in self.active_page_widgets:
            proxy_widget = self.active_page_widgets[page_index]
            page_widget = proxy_widget.widget()

            if isinstance(page_widget, PageGraphicsWidget):
                # Convert to page-local coordinates
                page_local_pos = scene_pos - proxy_widget.pos()
                page_widget.handle_mouse_event(event, page_local_pos)
                self.is_notebook_dirty = True
                return True

        return False

    def _handle_touch_event(self, event: object) -> bool:
        """Handle touch events and forward to appropriate page widget (future implementation)"""
        _ = event
        return False

    @override
    def keyPressEvent(self, event: QKeyEvent | None) -> None:
        """Close app with 'Q'"""
        if not event:
            return super().keyPressEvent(event)
        if event.key() == Qt.Key.Key_Q:
            self.logger.debug("Pressed 'Q', closing...")
            _ = self.close()
            sys.exit(0)
        return super().keyPressEvent(event)

    def _setup_save_worker(self):
        """Setup the Save Worker mechanism"""
        self.save_thread = QThread()
        self.save_worker = SaveWorker(
            self.notebook,
            settings.NOTEBOOK_FILE_PATH,
            self.key_buffer,
            self.salt,
            self.status_bar,
        )
        self.save_worker.moveToThread(self.save_thread)

        _ = self.save_thread.started.connect(self.save_worker.run)
        _ = self.save_worker.finished.connect(self.on_save_finished)
        _ = self.save_worker.error.connect(self.on_save_error)

        _ = self.save_worker.finished.connect(self.save_thread.quit)
        _ = self.save_thread.finished.connect(self.save_worker.deleteLater)
        _ = self.save_thread.finished.connect(self.save_thread.deleteLater)

    def save_async(self):
        """Save notebook in separate thread"""
        if self.is_saving:
            return
        self.is_saving = True
        self._setup_save_worker()
        self.logger.debug("Starting save on other thread")
        self.save_thread.start()

    def _add_page_below(self, page: Page) -> None:
        """Add a new page below the selected page"""
        page_index = self.pages_data.index(page)

        self.pages_data.insert(page_index + 1, Page())
        self.notebook.pages = self.pages_data

        # Refresh the layout
        self._reposition_all_pages()
        self.is_notebook_dirty = True

    def save(self):
        """Save notebook synchronously"""
        if self.is_notebook_dirty:
            self.logger.debug("Saving notebook (%d pages)...", len(self.notebook.pages))
            self.status_bar.showMessage("Saving...")
            try:
                NotebookDAO.save(
                    self.notebook,
                    settings.NOTEBOOK_FILE_PATH,
                    self.key_buffer,
                    self.salt,
                )
            except Exception as e:
                self.logger.error(e)
            self.status_bar.showMessage("Save completed!")
        else:
            self.logger.debug("Skipping save due to no changes")

        self.logger.debug("Creating backup...")
        self.status_bar.showMessage("Creating backup...")
        self.backup_manager.save_backups()
        self.status_bar.showMessage("Backup completed!")

    def _add_page_below_dynamic(self, page: Page) -> None:
        """Add a page below if this is the last page"""
        if self.notebook.pages[-1] == page:
            self._add_page_below(page)

    def _reposition_all_pages(self):
        """Reposition all pages to update the layout"""
        # Clear backgrounds
        for background in self.page_backgrounds.values():
            self.this_scene.removeItem(background)

        # Clear active widgets
        for proxy_widget in self.active_page_widgets.values():
            self.this_scene.removeItem(proxy_widget)
        self.active_page_widgets.clear()

        # Recreate layout
        self._layout_page_backgrounds()
        self._on_scroll()

    @override
    def closeEvent(self, a0: QCloseEvent | None):
        """Save notebook on close"""
        self.logger.debug("Close app event!")
        if a0 and self.notebook:
            settings.save_to_file(Path(SETTINGS_FILE_PATH))
            self.save()

    def on_save_finished(self, success: bool, message: str):
        """Save completed"""
        self.is_saving = False
        self.logger.debug("Save finished with result %s, message %s", success, message)

    def on_save_error(self, error_msg: str):
        """Save error occurred"""
        self.logger.error("Error while saving: %s", error_msg)
        self.is_saving = False

    def _get_current_page_index(self):
        """Estimate current page index based on viewport"""
        center_y = self.mapToScene(cast(QWidget, self.viewport()).rect().center()).y()
        page_height = settings.PAGE_HEIGHT + settings.PAGE_BETWEEN_SPACING
        return max(0, int(center_y / page_height))

    def scroll_to_page(self, page_index: int):
        """Scrolls to the selected page."""
        self.logger.debug("Scrolling to %s", page_index)
        if 0 <= page_index < len(self.pages_data):
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
        if self.pages_data:
            self.scroll_to_page(len(self.pages_data) - 1)

    def update_navbar(self):
        """Update navigation bar with current page info"""
        current_page = self._get_current_page_index()
        total_pages = len(self.pages_data)
        self.current_page_changed.emit(current_page, total_pages)

    @override
    def showEvent(self, event: QShowEvent | None) -> None:
        """Handle show event"""
        super().showEvent(event)
        if not self._initial_load_complete:
            self._initial_load_complete = True
            self.go_to_last_page()

    def select_tool(self, new_tool: Tool):
        settings.CURRENT_TOOL = new_tool
        self.logger.debug("Setting new tool: %s", new_tool)

        if new_tool != Tool.DRAG:
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
        else:
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        QApplication.setOverrideCursor(get_cursor_from_tool(new_tool))

    def change_color(self, new_color: QColor):
        settings.CURRENT_COLOR = new_color.name()
        self.logger.debug("Setting new color: %s", new_color)

    def change_thickness(self, new_thickness: float):
        settings.CURRENT_WIDTH = new_thickness
        self.logger.debug("Setting new thickness: %s", new_thickness)
