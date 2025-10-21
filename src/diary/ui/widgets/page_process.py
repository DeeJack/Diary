import logging
import pickle
from PyQt6.QtGui import QPixmap, QPainter, QColor
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QBuffer, QIODevice

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

    pixmap = QPixmap(dummy_widget.size())
    pixmap.fill(QColor(0xE0, 0xE0, 0xE0))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Use the dummy widget's methods to perform the drawing
    dummy_widget.draw_horizontal_lines(painter)
    dummy_widget.draw_previous_elements(painter)

    _ = painter.end()

    buffer = QBuffer()
    _ = buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    _ = pixmap.save(buffer, "PNG")  # Save as PNG format to the buffer

    return buffer.data().data()  # Return the raw bytes
