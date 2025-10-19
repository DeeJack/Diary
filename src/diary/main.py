"""
The main file that starts the Diary PyQt6 application
"""

import sys

from PyQt6.QtWidgets import QApplication

from diary.ui.main_window import MainWindow
from diary.logger import configure_logging

if __name__ == "__main__":
    configure_logging()

    app = QApplication([])
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec())
