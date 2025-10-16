import sys

from PyQt6.QtWidgets import (
    QInputDialog,
    QLineEdit,
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

        password_popup = QInputDialog(self)
        password_popup.setWindowTitle("Authentication")
        password_popup.setLabelText("Insert the password")
        password_popup.setTextEchoMode(QLineEdit.EchoMode.Password)
        _ = password_popup.accepted.connect(lambda: self.open_notebook(password_popup))  # pyright: ignore[reportUnknownMemberType]
        _ = password_popup.rejected.connect(lambda: self.close_app())  # pyright: ignore[reportUnknownMemberType]
        password_popup.open()  # pyright: ignore[reportUnknownMemberType]

    def open_notebook(self, password_popup: QInputDialog):
        print(password_popup.textValue())

        old_notebook = NotebookDAO.load(settings.NOTEBOOK_FILE_PATH)
        print(old_notebook)
        notebook = NotebookWidget(old_notebook)
        notebook.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCentralWidget(notebook)

    def close_app(self):
        _ = self.close()
        sys.exit(0)
