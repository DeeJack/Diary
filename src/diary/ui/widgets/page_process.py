"""Render a page in another process"""

import logging
import pickle

from PyQt6.QtCore import QBuffer, QIODevice, Qt
from PyQt6.QtGui import QColor, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication

from diary.config import settings
from diary.ui.widgets.page_widget import PageWidget


def render_page_in_process(pickled_page_data: bytes, page_index: int) -> bytes:
    """
    This function runs in a separate process to render a page.
    """
    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    logger: logging.Logger = logging.getLogger("PageProcess")
    logger.debug("Loading page")

    page = pickle.loads(pickled_page_data)
    dummy_widget = PageWidget(page, page_index)

    # Calculate high-resolution dimensions
    rendering_scale = settings.RENDERING_SCALE
    high_res_width = int(dummy_widget.size().width() * rendering_scale)
    high_res_height = int(dummy_widget.size().height() * rendering_scale)

    # Create high-resolution pixmaps
    final_pixmap = QPixmap(high_res_width, high_res_height)
    final_pixmap.fill(QColor(0xE0, 0xE0, 0xE0))

    stroke_buffer = QPixmap(high_res_width, high_res_height)
    stroke_buffer.fill(Qt.GlobalColor.transparent)

    # Set up high-resolution rendering for strokes
    buffer_painter = QPainter(stroke_buffer)
    buffer_painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    buffer_painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    buffer_painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
    # Scale the painter to render at high resolution
    buffer_painter.scale(rendering_scale, rendering_scale)

    dummy_widget.draw_previous_elements(buffer_painter)
    _ = buffer_painter.end()

    # Set up high-resolution rendering for final composition
    final_painter = QPainter(final_pixmap)
    final_painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    final_painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    final_painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
    # Scale the painter to render at high resolution
    final_painter.scale(rendering_scale, rendering_scale)

    dummy_widget.draw_horizontal_lines(final_painter)
    # Reset transformation for drawing the stroke buffer at correct scale
    final_painter.resetTransform()
    final_painter.drawPixmap(0, 0, stroke_buffer)
    _ = final_painter.end()

    buffer = QBuffer()
    _ = buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    _ = final_pixmap.save(buffer, "PNG")  # Save as PNG format to the buffer

    return buffer.data().data()  # Return the raw bytes
