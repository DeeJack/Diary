import logging
from typing import override
from PyQt6.QtCore import QObject, pyqtSignal, QRunnable, pyqtSlot
from PyQt6.QtGui import QPixmap, QPainter, QColor

from diary.ui.widgets.page_widget import PageWidget


class PageLoaderSignals(QObject):
    """
    Defines the signals available from a running worker thread.
    """

    finished: pyqtSignal = pyqtSignal(int, QPixmap)  # page_index, pixmap


class PageLoader(QRunnable):
    """
    Worker thread for rendering a Page to a QPixmap.
    """

    def __init__(self, page_index: int, page_widget: PageWidget):
        super().__init__()
        self.page_index: int = page_index
        self.page_widget: PageWidget = page_widget
        self.signals: PageLoaderSignals = PageLoaderSignals()

    @override
    @pyqtSlot(int, QPixmap)
    def run(self):
        """
        Renders the page content to a QPixmap.
        """
        logging.getLogger("PageWorker").debug("Loading page %d", self.page_index)
        pixmap = QPixmap(self.page_widget.size())
        pixmap.fill(QColor(0xE0, 0xE0, 0xE0))

        painter = QPainter(pixmap)
        # painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        self.page_widget.draw_horizontal_lines(painter)
        self.page_widget.draw_previous_elements(painter)

        _ = painter.end()

        # Notify finish signal
        self.signals.finished.emit(self.page_index, pixmap)
