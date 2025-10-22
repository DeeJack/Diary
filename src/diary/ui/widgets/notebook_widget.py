"""The widget for the Notebook containing the PageWidgets"""

from collections import deque
import logging
from multiprocessing import Pool
import pickle
from typing import cast, override
import sys

from PyQt6.QtGui import QCloseEvent, QPixmap, QTabletEvent, QWheelEvent, QKeyEvent
from PyQt6.QtWidgets import (
    QApplication,
    QGestureEvent,
    QGraphicsScene,
    QGraphicsView,
    QGraphicsProxyWidget,
    QScrollBar,
    QStatusBar,
    QWidget,
    QPinchGesture,
)
from PyQt6.QtCore import (
    QObject,
    QPoint,
    QPointF,
    QThread,
    QThreadPool,
    QTimer,
    Qt,
    QEvent,
    pyqtSlot,
)

from diary.ui.widgets.page_widget import PageWidget
from diary.models import Notebook, NotebookDAO, Page
from diary.config import settings
from diary.ui.widgets.save_worker import SaveWorker
from diary.utils.backup import BackupManager
from diary.utils.encryption import SecureBuffer
from diary.ui.widgets.page_process import render_page_in_process


class NotebookWidget(QGraphicsView):
    """The widget for the Notebook containing the PageWidgets"""

    def __init__(
        self,
        key_buffer: SecureBuffer,
        salt: bytes,
        status_bar: QStatusBar,
        notebook: Notebook | None = None,
    ):
        super().__init__()
        self.current_zoom: float = 0.7
        self.min_zoom: float = 0.4
        self.max_zoom: float = 1.3
        self.notebook: Notebook = notebook or Notebook([Page(), Page()])

        self.page_proxies: list[QGraphicsProxyWidget] = []
        self.key_buffer: SecureBuffer = key_buffer
        self.salt: bytes = salt
        self.backup_manager: BackupManager = BackupManager()
        self.logger: logging.Logger = logging.getLogger("NotebookWidget")
        self.loaded_pages: dict[int, QGraphicsProxyWidget] = {}
        self.load_distance: int = 2
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
        self.process_pool = Pool()

        # Caching/lazy load
        self.thread_pool: QThreadPool = QThreadPool()
        print(QThread.idealThreadCount())
        self.thread_pool.setMaxThreadCount(QThread.idealThreadCount())
        self.page_cache: dict[int, PageWidget] = {}  # {page_index: PageWidget}
        self.pages_to_load: set[int] = set()
        self.CACHE_SIZE: int = 3
        self.LOAD_THRESHOLD: int = 3

        self.high_priority_queue: deque[int] = deque()
        self.low_priority_queue: deque[int] = deque()
        self.loading_pages: set[int] = set()

        self.scroll_timer: QTimer = QTimer()
        self.scroll_timer.setSingleShot(True)
        self.scroll_timer.setInterval(150)
        _ = self.scroll_timer.timeout.connect(self._on_scroll)

        self.setup_notebook_widget()

    def setup_notebook_widget(self):
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
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setRenderHints(self.renderHints())
        QApplication.setOverrideCursor(Qt.CursorShape.BitmapCursor)

        # Setup save timer
        timer = QTimer(self)
        timer.setInterval(1000 * settings.AUTOSAVE_NOTEBOOK_TIMEOUT)
        _ = timer.timeout.connect(self.save_async)
        timer.start()

        # --- Initial Setup ---
        self._layout_pages()
        scrollbar = cast(QScrollBar, self.verticalScrollBar())
        _ = scrollbar.valueChanged.connect(self.on_scroll_timer)
        self._on_scroll()  # Initial load

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
                self.scale(scale_factor, scale_factor)
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

            # Zoom around mouse cursor position
            self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
            self.scale(zoom_factor, zoom_factor)
            self.current_zoom = new_zoom
            # Prevent event from scrolling
            event.accept()
        else:
            super().wheelEvent(event)

    @override
    def eventFilter(self, obj: QObject | None, event: QEvent | None) -> bool:  # pyright: ignore[reportIncompatibleMethodOverride]
        """Intercepts events to forward TabletEvents to the PageWidget"""
        if obj != self.viewport() or event is None or obj is None:
            return super().eventFilter(obj, event)

        if event.type() not in [
            QEvent.Type.TabletPress,
            QEvent.Type.TabletMove,
            QEvent.Type.TabletRelease,
        ] or not isinstance(event, QTabletEvent):
            return super().eventFilter(obj, event)

        # Save the notebook since it likely changed
        self.is_notebook_dirty = True

        # Get position in viewport
        pos: QPoint = event.position().toPoint()
        scene_pos: QPointF = self.mapToScene(pos)

        # Find page at position
        scene = self.scene()
        if scene is None:
            return super().eventFilter(obj, event)
        item = scene.itemAt(scene_pos, self.transform())

        if item and isinstance(item, QGraphicsProxyWidget):
            widget: QWidget | None = item.widget()
            if widget is None:
                return super().eventFilter(obj, event)

            if isinstance(widget, PageWidget):
                page_widget: PageWidget = widget
                # Map scene coordinates to page coordinates
                local_pos: QPointF = item.mapFromScene(scene_pos)
                # Forward event
                page_widget.handle_tablet_event(event, local_pos)
                return True  # Event handled
        return super().eventFilter(obj, event)

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

    def setup_save_worker(self):
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
        self.setup_save_worker()
        self.logger.debug("Starting save on other thread")
        self.save_thread.start()

    def add_page_below(self, page: Page) -> None:
        """Add a new page below the selected page"""
        self.logger.debug("Adding page below")
        index = self.notebook.pages.index(page) + 1
        new_page = Page()
        self.notebook.pages.insert(index, new_page)
        page_widget = PageWidget(new_page, index - 1)
        proxy = self.add_page_to_scene(page_widget)
        self.page_proxies.insert(index, proxy)
        self._reposition_all_pages()
        self.update()

    def save(self):
        """Save notebook synchronously"""
        if self.is_notebook_dirty:
            self.logger.debug("Saving notebook (%d pages)...", len(self.notebook.pages))
            self.status_bar.showMessage("Saving...")
            NotebookDAO.save(
                self.notebook, settings.NOTEBOOK_FILE_PATH, self.key_buffer, self.salt
            )
            self.status_bar.showMessage("Save completed!")
        else:
            self.logger.debug("Skipping save due to no changes")

        self.logger.debug("Creating backup...")
        self.status_bar.showMessage("Creating backup...")
        self.backup_manager.save_backups()
        self.status_bar.showMessage("Backup completed!")

    def add_page_below_dynamic(self, page: Page) -> None:
        """Add a page below if this is the last page"""
        if self.notebook.pages[-1] == page:
            self.add_page_below(page)

    def _reposition_all_pages(self) -> None:
        """Reposition all pages with correct spacing"""
        spacing = settings.PAGE_BETWEEN_SPACING
        y_position = 0
        for proxy in self.page_proxies:
            page_widget = cast(PageWidget, proxy.widget())
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

    def add_page_to_scene(self, page_widget: PageWidget):
        """Add a new PageWidget to the scene"""
        self.logger.debug("Adding page to the scene")
        proxy = self.this_scene.addWidget(page_widget)
        assert proxy is not None
        _ = page_widget.add_below.connect(
            lambda _: self.add_page_below(page_widget.page)
        )
        _ = page_widget.add_below_dynamic.connect(
            lambda _: self.add_page_below_dynamic(page_widget.page)
        )
        _ = page_widget.needs_regeneration.connect(self.regenerate_page)
        return proxy

    def _layout_pages(self):
        """Setup the layout for the pages, without loading them"""
        y_pos = 0
        for i, page_data in enumerate(self.notebook.pages):
            page_widget = PageWidget(page_data, i)
            proxy_widget = self.add_page_to_scene(page_widget)
            proxy_widget.setPos(0, y_pos)
            self.page_proxies.append(proxy_widget)
            self.page_cache[i] = page_widget  # No content yet
            y_pos += page_widget.height() + settings.PAGE_BETWEEN_SPACING

    def on_scroll_timer(self, _):
        """Call the timer to load the new pages, overriding the previous timer if already called"""
        try:
            self.scroll_timer.start()
        except Exception as _:
            pass  # Object has been destroyed

    def _on_scroll(self):
        """Load the new visible pages after scrolling"""
        visible_indices = self._get_visible_page_indices()
        current_page_index = self._get_current_page_index()

        start_page = max(0, current_page_index - (self.CACHE_SIZE // 2))
        end_page = min(len(self.page_proxies), start_page + self.CACHE_SIZE)

        # Unload pages outside the cached window
        for index, proxy in enumerate(self.page_proxies):
            page_widget: PageWidget = cast(PageWidget, proxy.widget())
            if not (start_page <= index < end_page) and page_widget.is_loaded:
                page_widget.backing_pixmap = None
                page_widget.is_loaded = False
                page_widget.update()  # Redraw as a placeholder

        # Queue pages for loading
        self.high_priority_queue.clear()
        self.low_priority_queue.clear()

        for i in range(start_page, end_page):
            page_widget = cast(PageWidget, self.page_proxies[i].widget())
            if not page_widget.is_loaded and i not in self.loading_pages:
                if i in visible_indices:
                    self.high_priority_queue.append(i)
                else:
                    self.low_priority_queue.append(i)

        self._dispatch_tasks()

    def _get_current_page_index(self):
        """Estimate current page index based on viewport"""
        center_y = self.mapToScene(self.viewport().rect().center()).y()  # pyright: ignore[reportOptionalMemberAccess]
        page_height = settings.PAGE_HEIGHT + settings.PAGE_BETWEEN_SPACING
        return max(0, int(center_y / page_height))

    def _get_visible_page_indices(self) -> set[int]:
        """Determines which pages are currently visible in the viewport."""
        visible_rect = self.mapToScene(
            cast(QWidget, self.viewport()).rect()
        ).boundingRect()
        visible_indices: set[int] = set()
        for index, proxy in enumerate(self.page_proxies):
            if proxy.sceneBoundingRect().intersects(visible_rect):
                visible_indices.add(index)
        return visible_indices

    def _dispatch_tasks(self):
        """Starts new workers from the queues if there's capacity."""
        if not self.high_priority_queue and not self.low_priority_queue:
            return

        for _ in range(QThread.idealThreadCount()):
            # Simplified: just dispatch one task for now
            if self.high_priority_queue:
                page_index = self.high_priority_queue.popleft()
            elif self.low_priority_queue:
                page_index = self.low_priority_queue.popleft()
            else:
                break

            if page_index not in self.loading_pages:
                self.loading_pages.add(page_index)
                self.logger.debug("Loading page %d on another process", page_index)

                # Get the serializable data
                page_widget = cast(PageWidget, self.page_proxies[page_index].widget())
                page_data = page_widget.page
                pickled_page_data = pickle.dumps(page_data)

                # Send the job to the worker process
                _ = self.process_pool.apply_async(
                    render_page_in_process,
                    args=(pickled_page_data, page_index),
                    callback=lambda result_bytes,
                    p_index=page_index: self.on_page_loaded(p_index, result_bytes),
                )

    def on_page_loaded(self, page_index: int, png_bytes: bytes):
        """Slot to receive the rendered pixmap from a worker."""
        self.logger.debug("Page %d loaded", page_index)

        if page_index in self.loading_pages:
            self.loading_pages.remove(page_index)

        page_widget = cast(PageWidget, self.page_proxies[page_index].widget())

        # Recreate the QPixmap from the raw PNG data
        pixmap = QPixmap()
        _ = pixmap.loadFromData(png_bytes)

        page_widget.set_backing_pixmap(pixmap)

        # Since a task finished, try to dispatch the next one from the queue
        self._dispatch_tasks()

    @pyqtSlot(int)
    def regenerate_page(self, page_index: int):
        """
        Queues a high-priority job to re-render a specific page.
        This is called when a page's content (e.g., erasing) has changed.
        """
        self.logger.debug("Queueing high-priority regeneration for page %d", page_index)
        self.high_priority_queue.appendleft(page_index)
        # Request the refresh immediately
        self._dispatch_tasks()
