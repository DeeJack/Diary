from PyQt6.QtWidgets import QGestureEvent, QGraphicsScene, QGraphicsView
from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtGui import QNativeGestureEvent, QWheelEvent
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

        self.pages = [PageWidget(), PageWidget()]

        y_position = 0
        spacing = 10
        scene = self.scene()
        assert scene is not None

        for page_widget in self.pages:
            proxy = scene.addWidget(page_widget)
            assert proxy is not None
            proxy.setPos(0, y_position)
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
                scale_factor = pinch.scaleFactor()  # type: ignore
                self.scale(scale_factor, scale_factor)
                return True

        return super().viewportEvent(event)

    def wheelEvent(self, event):
        # Check if Ctrl is pressed
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # Get zoom direction
            delta = event.angleDelta().y()

            if delta > 0:
                # Zoom in
                zoom_factor = 1.15
            else:
                # Zoom out
                zoom_factor = 1 / 1.15

            # Zoom around mouse cursor position
            self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
            self.scale(zoom_factor, zoom_factor)

            # Prevent event from scrolling
            event.accept()
        else:
            # Normal scroll behavior
            super().wheelEvent(event)
