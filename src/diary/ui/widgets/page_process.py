import logging
import pickle
from PyQt6.QtGui import QPixmap, QPainter, QColor
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QBuffer, QIODevice, Qt

from diary.ui.widgets.page_widget import PageWidget


def render_page_in_process(pickled_page_data: bytes) -> bytes:
    """
    This function runs in a separate process to render a page.
    It returns the rendered page as PNG bytes.
    """
    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    logger: logging.Logger = logging.getLogger("PageProcess")
    logger.debug("Loading page")

    page = pickle.loads(pickled_page_data)
    dummy_widget = PageWidget(page)

    final_pixmap = QPixmap(dummy_widget.size())
    final_pixmap.fill(QColor(0xE0, 0xE0, 0xE0))

    stroke_buffer = QPixmap(dummy_widget.size())
    stroke_buffer.fill(Qt.GlobalColor.transparent)

    buffer_painter = QPainter(stroke_buffer)
    buffer_painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    dummy_widget.draw_previous_elements(buffer_painter)
    _ = buffer_painter.end()

    final_painter = QPainter(final_pixmap)
    final_painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    dummy_widget.draw_horizontal_lines(final_painter)
    final_painter.drawPixmap(0, 0, stroke_buffer)
    _ = final_painter.end()

    buffer = QBuffer()
    _ = buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    _ = final_pixmap.save(buffer, "PNG")  # Save as PNG format to the buffer

    return buffer.data().data()  # Return the raw bytes
