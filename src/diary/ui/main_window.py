from PyQt6.QtWidgets import (
    QMainWindow,
)
from PyQt6.QtCore import Qt

from diary.models import NotebookDAO
from diary.ui.widgets.notebook_widget import NotebookWidget
from diary.config import settings


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Diary Application")
        self.setGeometry(100, 100, 800, 600)
        self.setStyleSheet("background-color: #2C2C2C;")

        old_notebook = NotebookDAO.load(settings.NOTEBOOK_FILE_PATH)
        print(old_notebook)
        notebook = NotebookWidget(old_notebook)
        notebook.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCentralWidget(notebook)
