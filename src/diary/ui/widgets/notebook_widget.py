from PyQt6.QtWidgets import (
    QGestureEvent,
    QGraphicsScene,
    QGraphicsView,
    QGraphicsItem,
    QGraphicsProxyWidget,
)
from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtGui import QTabletEvent
from PyQt6.QtCore import Qt


from diary.ui.widgets.page_widget import PageWidget


class NotebookWidget(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene())

        self.viewport().setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents)
        self.viewport().grabGesture(
            Qt.GestureType.PinchGesture, Qt.GestureFlag.ReceivePartialGestures
        )
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.viewport().installEventFilter(self)

        self.pages = [PageWidget(), PageWidget()]
        self.current_zoom = 1
        self.min_zoom = 0.5
        self.max_zoom = 1.5

        y_position = 0
        spacing = 10
        scene = self.scene()
        assert scene is not None

        for page_widget in self.pages:
            proxy = scene.addWidget(page_widget)
            assert proxy is not None
            proxy.setPos(0, y_position)
            proxy.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable, True)
            proxy.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)

            # Make sure events propagate
            proxy.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
            y_position += page_widget.height() + spacing

    def viewportEvent(self, event: QEvent | None):
        print(event)
        if event is None or not isinstance(event, QGestureEvent):
            return super().viewportEvent(event)

        if event.type() == QEvent.Type.Gesture:
            pinch = event.gesture(Qt.GestureType.PinchGesture)
            if pinch and pinch.state() == Qt.GestureState.GestureUpdated:
                # Scale view around center point
                self.setTransformationAnchor(
                    QGraphicsView.ViewportAnchor.AnchorUnderMouse
                )

                scale_factor = self.current_zoom * pinch.scaleFactor()  # type: ignore
                new_zoom = max(
                    self.min_zoom * 1.15, min(scale_factor, self.max_zoom * 1.15)
                )
                scale_factor = new_zoom / self.current_zoom
                self.scale(scale_factor, scale_factor)
                self.current_zoom = new_zoom

                return True

        return super().viewportEvent(event)

    def wheelEvent(self, event):
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

    def eventFilter(self, obj, event):
        """Intercept events on viewport"""

        if obj == self.viewport():
            if event.type() in [
                QEvent.Type.TabletPress,
                QEvent.Type.TabletMove,
                QEvent.Type.TabletRelease,
            ]:
                # Get position in viewport
                pos = event.position().toPoint()

                # Map to scene
                scene_pos = self.mapToScene(pos)

                # Find page at position
                item = self.scene().itemAt(scene_pos, self.transform())

                if item and isinstance(item, QGraphicsProxyWidget):
                    page_widget = item.widget()

                    # Map to page coordinates
                    local_pos = page_widget.mapFromGlobal(self.mapToGlobal(pos))

                    # Forward event
                    page_widget.handle_tablet_event(event, local_pos)

                    return True  # Event handled

        return super().eventFilter(obj, event)
