"""
The main file that starts the Diary PyQt6 application
"""

import sys
import logging

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from diary.ui.main_window import MainWindow
from diary.logger import configure_logging


if __name__ == "__main__":
    configure_logging()
    logging.debug("Starting the application...")

    # Enable high-DPI display support for crisp rendering
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication([])

    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec())
