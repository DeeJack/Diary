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
from PyQt6.QtCore import QPoint, QPointF, Qt, QEvent

from diary.ui.widgets.page_widget import PageWidget


class NotebookWidget(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene())

        # Accept events, handle dragging...
        current_viewport = self.viewport()
        assert current_viewport is not None
        current_viewport.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents)
        current_viewport.grabGesture(
            Qt.GestureType.PinchGesture, Qt.GestureFlag.ReceivePartialGestures
        )
        current_viewport.installEventFilter(self)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

        self.pages: list[PageWidget] = [PageWidget(None), PageWidget(None)]
        self.current_zoom: float = 1
        self.min_zoom: float = 0.5
        self.max_zoom: float = 1.5

        # Add all the pages
        y_position = 0
        spacing = 10
        scene = self.scene()
        assert scene is not None
        for page_widget in self.pages:
            proxy = scene.addWidget(page_widget)
            assert proxy is not None
            proxy.setPos(0, y_position)
            y_position += page_widget.height() + spacing

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
    def eventFilter(self, obj: QWidget, event: QEvent) -> bool:  # pyright: ignore[reportIncompatibleMethodOverride]
        """Intercepts events to forward TabletEvents to the PageWidget"""
        if obj != self.viewport():
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
                # Map to page coordinates
                local_pos: QPoint = page_widget.mapFromGlobal(self.mapToGlobal(pos))
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
