"""Graphics item for rendering video elements using QGraphicsItem architecture."""

import logging
import os
import tempfile
from typing import cast, override

from PyQt6.QtCore import QPointF, QRectF, Qt, QUrl
from PyQt6.QtGui import QColor, QPainter, QPen, QPixmap, QPolygonF
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import (
    QDialog,
    QGraphicsItem,
    QGraphicsSceneMouseEvent,
    QStyleOptionGraphicsItem,
    QVBoxLayout,
    QWidget,
)

from diary.config import settings
from diary.models.elements.video import Video
from diary.models.point import Point

from .resizable_graphics_item import ResizableGraphicsItem


class VideoGraphicsItem(ResizableGraphicsItem):
    """Graphics item for rendering video elements with resize handles."""

    def __init__(self, video_element: Video, parent: QGraphicsItem | None = None):
        super().__init__(video_element, parent)
        self._logger: logging.Logger = logging.getLogger("VideoGraphicsItem")
        self._thumbnail: QPixmap | None = None

        # Configure item flags for videos
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)

        self.setPos(video_element.position.x, video_element.position.y)
        self.setTransformOriginPoint(video_element.width / 2, video_element.height / 2)
        self._load_thumbnail()

    @property
    def video_element(self) -> Video:
        """Get the video element."""
        return cast(Video, self._element)

    @override
    def _calculate_bounding_rect(self) -> QRectF:
        """Calculate the bounding rectangle for the video."""
        rect = QRectF(0, 0, self.video_element.width, self.video_element.height)
        padding = 10.0
        return rect.adjusted(-padding, -padding, padding, padding)

    @override
    def paint(
        self,
        painter: QPainter | None,
        option: QStyleOptionGraphicsItem | None,
        widget: QWidget | None = None,
    ) -> None:
        """Paint a video placeholder with selection and resize handles."""
        if not painter:
            return

        self.configure_painter_quality(painter)

        if self.isSelected():
            self._draw_selection_highlight(painter)

        painter.save()

        if self.video_element.rotation != 0.0:
            center_x = self.video_element.width / 2
            center_y = self.video_element.height / 2
            painter.translate(center_x, center_y)
            painter.rotate(self.video_element.rotation)
            painter.translate(-center_x, -center_y)

        rect = QRectF(0, 0, self.video_element.width, self.video_element.height)
        if self._thumbnail and not self._thumbnail.isNull():
            painter.drawPixmap(rect, self._thumbnail, self._thumbnail.rect().toRectF())
            painter.setPen(QPen(QColor(40, 40, 40), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect)
            self._draw_play_icon(painter, rect)
        else:
            painter.fillRect(rect, QColor(30, 30, 30))
            painter.setPen(QPen(QColor(80, 80, 80), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect)
            self._draw_play_icon(painter, rect)

        painter.restore()

        if self.isSelected():
            self._draw_resize_handles(painter)

    def _draw_selection_highlight(self, painter: QPainter) -> None:
        """Draw selection highlight around the video."""
        rect = QRectF(
            -2,
            -2,
            self.video_element.width + 4,
            self.video_element.height + 4,
        )
        selection_pen = QPen(QColor(0, 120, 255), 2, Qt.PenStyle.SolidLine)
        painter.setPen(selection_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(rect)

    def _draw_play_icon(self, painter: QPainter, rect: QRectF) -> None:
        """Draw a simple play icon centered in the video rect."""
        size = min(rect.width(), rect.height()) * 0.3
        center = rect.center()
        half_size = size / 2

        points = [
            QPointF(center.x() - half_size * 0.6, center.y() - half_size),
            QPointF(center.x() - half_size * 0.6, center.y() + half_size),
            QPointF(center.x() + half_size, center.y()),
        ]

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(220, 220, 220))
        painter.drawPolygon(QPolygonF(points))

    def _load_thumbnail(self) -> None:
        """Load thumbnail pixmap from the video element data."""
        self._thumbnail = None
        if not self.video_element.thumbnail_data:
            return

        pixmap = QPixmap()
        if pixmap.loadFromData(self.video_element.thumbnail_data):
            self._thumbnail = pixmap
        else:
            self._logger.debug("Failed to load video thumbnail data")

    @override
    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent | None) -> None:
        """Open a video player dialog on double click."""
        if event and event.button() == Qt.MouseButton.LeftButton:
            self._open_video_dialog()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def _open_video_dialog(self) -> None:
        """Play the video in a modal dialog."""
        if not self.video_element.video_data:
            self._logger.debug("Video data not available for playback")
            return

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        _ = temp_file.write(self.video_element.video_data)
        temp_file.flush()
        temp_file.close()

        dialog = QDialog()
        dialog.setWindowTitle("Video")
        dialog.setMinimumSize(640, 360)

        layout = QVBoxLayout(dialog)
        video_widget = QVideoWidget(dialog)
        layout.addWidget(video_widget)

        audio_output = QAudioOutput(dialog)
        player = QMediaPlayer(dialog)
        player.setAudioOutput(audio_output)
        player.setVideoOutput(video_widget)
        player.setSource(QUrl.fromLocalFile(temp_file.name))
        player.play()

        def cleanup() -> None:
            player.stop()
            try:
                os.unlink(temp_file.name)
            except OSError:
                pass

        _ = dialog.finished.connect(lambda _: cleanup())
        _ = dialog.exec()

    @override
    def _update_element_position(self, new_position: QPointF) -> None:
        """Update the video element's position when the graphics item moves."""
        if (
            0 <= new_position.x() <= settings.PAGE_WIDTH
            and 0 <= new_position.y() <= settings.PAGE_HEIGHT
        ):
            self.video_element.position = Point(new_position.x(), new_position.y(), 0)

    def set_size(self, width: float, height: float) -> None:
        """Update the video size."""
        self.video_element.width = width
        self.video_element.height = height
        self.setTransformOriginPoint(width / 2, height / 2)
        self.invalidate_cache()

    @override
    def _get_current_size(self) -> tuple[float, float]:
        """Return current video size."""
        return (self.video_element.width, self.video_element.height)

    @override
    def _apply_resize(
        self, new_size: tuple[float, float], new_scene_pos: QPointF
    ) -> None:
        """Apply resize updates for the video element."""
        self.set_size(new_size[0], new_size[1])

        if new_scene_pos != self.pos():
            self.video_element.position = Point(
                new_scene_pos.x(),
                new_scene_pos.y(),
                self.video_element.position.pressure,
            )
            self.setPos(new_scene_pos)

    @override
    def type(self) -> int:
        """Return unique type identifier for video items."""
        return hash("VideoGraphicsItem") & 0x7FFFFFFF

    def clone(self) -> "VideoGraphicsItem":
        """Create a copy of this video graphics item."""
        new_video = Video(
            position=Point(
                self.video_element.position.x,
                self.video_element.position.y,
                self.video_element.position.pressure,
            ),
            width=self.video_element.width,
            height=self.video_element.height,
            asset_id=self.video_element.asset_id,
            rotation=self.video_element.rotation,
            duration=self.video_element.duration,
            thumbnail_data=self.video_element.thumbnail_data,
            thumbnail_asset_id=self.video_element.thumbnail_asset_id,
        )
        new_video.video_data = self.video_element.video_data
        return VideoGraphicsItem(new_video)
