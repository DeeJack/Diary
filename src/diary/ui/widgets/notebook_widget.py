"""The widget for the Notebook containing the PageWidgets"""

import logging
import sys
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
    pyqtSlot,  # pyright: ignore[reportUnknownVariableType]
)
from PyQt6.QtGui import (
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
    QGraphicsScene,
    QGraphicsView,
    QPinchGesture,
    QPushButton,
    QScrollBar,
    QStatusBar,
    QWidget,
)

from diary.config import settings
from diary.models import Notebook, NotebookDAO, Page
from diary.ui.graphics_items.page_graphics_widget import PageGraphicsWidget
from diary.ui.widgets.save_worker import SaveWorker
from diary.ui.widgets.tool_selector import Tool
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

        self.page_proxies: list[QGraphicsProxyWidget] = []
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
        self._layout_pages()

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

        # Setup save timer
        timer = QTimer(self)
        timer.setInterval(1000 * settings.AUTOSAVE_NOTEBOOK_TIMEOUT)
        _ = timer.timeout.connect(self.save_async)
        timer.start()

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
        if isinstance(event, QMouseEvent):
            return self._handle_mouse_event(event)

        # Handle touch events for drawing
        if isinstance(event, QTouchEvent):
            return self._handle_touch_event(event)

        return super().eventFilter(obj, event)

    def _handle_tablet_event(self, event: QTabletEvent) -> bool:
        """Handle tablet events and forward to appropriate page widget"""

        # Save the notebook since it likely changed
        self.is_notebook_dirty = True

        # Get position in viewport
        pos: QPoint = event.position().toPoint()
        scene_pos: QPointF = self.mapToScene(pos)

        # Find page at position
        scene = self.scene()
        if scene is None:
            return False
        item = scene.itemAt(scene_pos, self.transform())

        if item and isinstance(item, QGraphicsProxyWidget):
            widget: QWidget | None = item.widget()
            if widget is None:
                return False

            if isinstance(widget, PageGraphicsWidget):
                page_widget: PageGraphicsWidget = widget
                # Map scene coordinates to page coordinates
                local_pos: QPointF = item.mapFromScene(scene_pos)
                # Forward event
                page_widget.handle_tablet_event(
                    event,
                    local_pos,
                )
                return True  # Event handled

        event.ignore()
        return False

    def _handle_mouse_event(self, event: QMouseEvent) -> bool:
        """Handle mouse events and forward to appropriate page widget"""
        # Only handle left mouse button for drawing
        if (
            event.button() != Qt.MouseButton.LeftButton
            and event.type() != QMouseEvent.Type.MouseMove
        ):
            return False

        # Get position in viewport
        pos: QPoint = event.position().toPoint()
        scene_pos: QPointF = self.mapToScene(pos)

        # Find page at position
        scene = self.scene()
        if scene is None:
            return False
        item = scene.itemAt(scene_pos, self.transform())

        if item and isinstance(item, QGraphicsProxyWidget):
            widget: QWidget | None = item.widget()
            if widget is None:
                return False

            if isinstance(widget, PageGraphicsWidget):
                page_widget: PageGraphicsWidget = widget
                # Map scene coordinates to page coordinates
                local_pos: QPointF = item.mapFromScene(scene_pos)

                child_widget = page_widget.childAt(local_pos.toPoint())
                if child_widget and isinstance(child_widget, QPushButton):
                    # Let the button handle the event normally
                    return False

                # Save the notebook since it likely changed
                self.is_notebook_dirty = True
                page_widget.handle_mouse_event(event, local_pos)
                return True
        event.ignore()
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
        self.logger.debug("Adding page below")
        index = self.notebook.pages.index(page) + 1
        new_page = Page()
        self.notebook.pages.insert(index, new_page)
        page_widget = PageGraphicsWidget(new_page, index - 1)
        proxy = self._add_page_to_scene(page_widget)
        self.page_proxies.insert(index, proxy)
        self._reposition_all_pages()
        self.update()

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

    def _reposition_all_pages(self) -> None:
        """Reposition all pages with correct spacing"""
        spacing = settings.PAGE_BETWEEN_SPACING
        y_position = 0
        for proxy in self.page_proxies:
            page_widget = cast(PageGraphicsWidget, proxy.widget())
            proxy.setPos(0, y_position)
            y_position += page_widget.height() + spacing

    @override
    def closeEvent(self, a0: QCloseEvent | None):
        """Save notebook on close"""
        self.logger.debug("Close app event!")
        if a0 and self.notebook:
            self.save()
            a0.accept()

    def on_save_finished(self, success: bool, message: str):
        """Save completed"""
        self.is_saving = False
        self.logger.debug("Save finished with result %s, message %s", success, message)

    def on_save_error(self, error_msg: str):
        """Save error occurred"""
        self.logger.error("Error while saving: %s", error_msg)
        self.is_saving = False

    def cancel_save(self):
        """Cancel ongoing save operation"""
        if self.save_worker:
            self.save_worker.cancel()

    def _add_page_to_scene(self, page_widget: PageGraphicsWidget):
        """Add a new PageWidget to the scene"""
        proxy = self.this_scene.addWidget(page_widget)
        assert proxy is not None
        _ = page_widget.add_below.connect(
            lambda _: self._add_page_below(page_widget.page)
        )
        _ = page_widget.add_below_dynamic.connect(
            lambda _: self._add_page_below_dynamic(page_widget.page)
        )
        return proxy

    def _layout_pages(self):
        """Setup the layout for the pages, without loading them"""
        y_pos = 0
        for i, page_data in enumerate(self.notebook.pages):
            page_widget = PageGraphicsWidget(page_data, i)
            proxy_widget = self._add_page_to_scene(page_widget)
            proxy_widget.setPos(0, y_pos)
            self.page_proxies.append(proxy_widget)
            # self.page_cache[i] = page_widget  # No content yet
            y_pos += page_widget.height() + settings.PAGE_BETWEEN_SPACING

    def _get_current_page_index(self):
        """Estimate current page index based on viewport"""
        center_y = self.mapToScene(cast(QWidget, self.viewport()).rect().center()).y()
        page_height = settings.PAGE_HEIGHT + settings.PAGE_BETWEEN_SPACING
        return max(0, int(center_y / page_height))

    def scroll_to_page(self, page_index: int):
        """Scrolls to the selected page."""
        self.logger.debug("Scrolling to %s", page_index)
        if 0 <= page_index < len(self.notebook.pages):
            # Calculate the Y position of the target page
            y_pos = page_index * (settings.PAGE_HEIGHT + settings.PAGE_BETWEEN_SPACING)
            cast(QScrollBar, self.verticalScrollBar()).setValue(int(y_pos))

    @pyqtSlot()  # pyright: ignore[reportUntypedFunctionDecorator]
    def go_to_first_page(self):
        """PyQtSlot to scroll to the first page"""
        self.scroll_to_page(0)

    @pyqtSlot()  # pyright: ignore[reportUntypedFunctionDecorator]
    def go_to_last_page(self):
        """PyQtSlot to scroll to the last page"""
        total_pages = len(self.notebook.pages)
        if total_pages > 0:
            self.scroll_to_page(total_pages - 1)

    def update_navbar(self):
        """Updates the indexes for the Page Navigator"""
        self.current_page_changed.emit(
            self._get_current_page_index(), len(self.notebook.pages)
        )

    @override
    def showEvent(self, event: QShowEvent | None) -> None:
        """
        Overrides the show event to scroll to the last page on initial startup.
        """
        super().showEvent(event)

        if not self._initial_load_complete:
            QTimer.singleShot(5, self.go_to_last_page)
            self._initial_load_complete = True

    def select_tool(self, new_tool: Tool):
        settings.CURRENT_TOOL = new_tool
        self.logger.debug("Setting new tool: %s", new_tool)

        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        match new_tool:
            case Tool.TEXT:
                QApplication.setOverrideCursor(Qt.CursorShape.IBeamCursor)
            case Tool.PEN:
                QApplication.setOverrideCursor(Qt.CursorShape.CrossCursor)
            case Tool.ERASER:
                QApplication.setOverrideCursor(Qt.CursorShape.ForbiddenCursor)
            case Tool.DRAG:
                QApplication.setOverrideCursor(Qt.CursorShape.OpenHandCursor)
                self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            case Tool.IMAGE:
                QApplication.setOverrideCursor(Qt.CursorShape.CrossCursor)
            case Tool.AUDIO:
                QApplication.setOverrideCursor(Qt.CursorShape.CrossCursor)
            case Tool.SELECTION:
                QApplication.setOverrideCursor(Qt.CursorShape.ArrowCursor)

    def change_color(self, new_color: QColor):
        settings.CURRENT_COLOR = new_color
        self.logger.debug("Setting new color: %s", new_color)

    def change_thickness(self, new_thickness: float):
        settings.CURRENT_WIDTH = new_thickness
        self.logger.debug("Setting new thickness: %s", new_thickness)
