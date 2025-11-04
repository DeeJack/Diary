"""
The main file that starts the Diary PyQt6 application
"""

import ctypes
import logging
import os
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from diary.config import settings
from diary.logger import configure_logging
from diary.ui.main_window import MainWindow

if __name__ == "__main__":
    os.makedirs(settings.DATA_DIR_PATH, exist_ok=True)
    configure_logging()
    logging.debug("Starting the application...")

    # Enable high-DPI display support for crisp rendering
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    ctypes.windll.shcore.SetProcessDpiAwareness(True)

    app = QApplication([])

    try:
        main_window = MainWindow()
        main_window.showMaximized()
        sys.exit(app.exec())
    except Exception as e:  # pylint: disable=broad-exception-caught
        logging.getLogger("MainWindow").error("Uncaught exception: %s", e)
