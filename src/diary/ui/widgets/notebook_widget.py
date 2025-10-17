from typing import override
import sys

from PyQt6.QtGui import QTabletEvent, QWheelEvent, QKeyEvent
from PyQt6.QtWidgets import (
    QGestureEvent,
    QGraphicsScene,
    QGraphicsView,
    QGraphicsProxyWidget,
    QWidget,
    QPinchGesture,
)
from PyQt6.QtCore import QObject, QPoint, QPointF, Qt, QEvent

from diary.ui.widgets.page_widget import PageWidget
from diary.models import Notebook, NotebookDAO, Page
from diary.config import settings
from diary.utils.encryption import SecureBuffer


class NotebookWidget(QGraphicsView):
    def __init__(
        self, key_buffer: SecureBuffer, salt: bytes, notebook: Notebook | None = None
    ):
        super().__init__()
        self.current_zoom: float = 0.7
        self.min_zoom: float = 0.4
        self.max_zoom: float = 1.3
        self.notebook: Notebook = notebook or Notebook([Page(), Page()])
        self.pages: list[PageWidget] = [
            PageWidget(page) for page in self.notebook.pages
        ]
        self.page_proxies: list[QGraphicsProxyWidget] = []
        self.key_buffer: SecureBuffer = key_buffer
        self.salt: bytes = salt

        self.this_scene: QGraphicsScene = QGraphicsScene()
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

        # Add all the pages
        self.y_position: int = 0
        spacing = settings.PAGE_BETWEEN_SPACING
        for page_widget in self.pages:
            proxy = self.add_page_to_scene(page_widget)
            self.page_proxies.append(proxy)
            proxy.setPos(0, self.y_position)
            self.y_position += page_widget.height() + spacing

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

                scale_factor: float = self.current_zoom * pinch.scaleFactor()  # type: ignore
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
            return
        if event.key() == Qt.Key.Key_Q:
            sys.exit(0)
        return super().keyPressEvent(event)

    def save_notebook(self):
        """Saves the notebook to file"""
        NotebookDAO.save(
            self.notebook, settings.NOTEBOOK_FILE_PATH, self.key_buffer, self.salt
        )

    def add_page_to_scene(self, page_widget: PageWidget):
        """Add a new PageWidget to the scene"""
        proxy = self.this_scene.addWidget(page_widget)
        assert proxy is not None
        _ = page_widget.add_below.connect(  # pyright: ignore[reportUnknownMemberType]
            lambda _: self.add_page_below(page_widget.page)  # pyright: ignore[reportUnknownLambdaType]
        )
        _ = page_widget.save_notebook.connect(lambda: self.save_notebook())  # pyright: ignore[reportUnknownMemberType]
        _ = page_widget.add_below_dynamic.connect(  # pyright: ignore[reportUnknownMemberType]
            lambda _: self.add_page_below_dynamic(page_widget.page)  # pyright: ignore[reportUnknownLambdaType  # pyright: ignore[reportUnknownLambdaType]
        )
        return proxy

    def add_page_below(self, page: Page) -> None:
        """Add a new page below the selected page"""
        index = self.notebook.pages.index(page) + 1
        new_page = Page()
        self.notebook.pages.insert(index, new_page)
        page_widget = PageWidget(new_page)
        self.pages.insert(index, page_widget)
        proxy = self.add_page_to_scene(page_widget)
        self.page_proxies.insert(index, proxy)
        self._reposition_all_pages()
        self.update()

    def add_page_below_dynamic(self, page: Page) -> None:
        """Add a page below if this is the last page"""
        if self.notebook.pages[-1] == page:
            self.add_page_below(page)

    def _reposition_all_pages(self) -> None:
        """Reposition all pages with correct spacing"""
        spacing = settings.PAGE_BETWEEN_SPACING
        y_position = 0
        for _, (page_widget, proxy) in enumerate(zip(self.pages, self.page_proxies)):
            proxy.setPos(0, y_position)
            y_position += page_widget.height() + spacing
