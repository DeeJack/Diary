"""
The main file that starts the Diary PyQt6 application
"""

import faulthandler
import logging
import os
import sys
import traceback
from types import TracebackType

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QMessageBox

from diary.config import settings
from diary.logger import configure_logging
from diary.ui.main_window import MainWindow


def global_exception_handler(
    exc_type: type, exc_value: Exception, exc_traceback: TracebackType
):
    """Handle uncaught exceptions globally."""
    logger = logging.getLogger("GlobalExceptionHandler")

    # Format the full traceback
    error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))

    # Log the exception
    logger.critical("Uncaught exception:\n%s", error_msg)

    # Show error dialog to user
    try:
        _ = QMessageBox.critical(
            None,
            "Unexpected Error",
            f"An unexpected error occurred:\n\n{exc_value}\n\nThe error has been logged. "
            + "Please check the logs for more details.",
        )
    except Exception:  # pylint: disable=broad-exception-caught
        # If we can't show the dialog, at least print to stderr
        if sys.stderr is not None:
            print(error_msg, file=sys.stderr)

    # Call the default exception handler
    sys.__excepthook__(exc_type, exc_value, exc_traceback)


if __name__ == "__main__":
    os.makedirs(settings.DATA_DIR_PATH, exist_ok=True)
    configure_logging()
    logging.debug("Starting the application...")

    # Enable faulthandler to catch segmentation faults
    if sys.stderr is not None:
        faulthandler.enable()

    # Set up global exception handler
    sys.excepthook = global_exception_handler

    # Enable high-DPI display support for crisp rendering
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication([])

    try:
        main_window = MainWindow()
        main_window.showMaximized()
        sys.exit(app.exec())
    except Exception as e:  # pylint: disable=broad-exception-caught
        logging.getLogger("MainWindow").error("Uncaught exception: %s", e)
