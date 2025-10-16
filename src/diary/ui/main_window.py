from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
)
from PyQt6.QtCore import Qt

from diary.ui.widgets.notebook_widget import NotebookWidget
from diary.ui.widgets.page_widget import PageWidget


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Diary Application")
        self.setGeometry(100, 100, 800, 600)
        self.setStyleSheet("background-color: #2C2C2C;")

        # central_widget = QWidget()
        # layout = QVBoxLayout(central_widget)
        # layout.addWidget(PageWidget(), alignment=Qt.AlignmentFlag.AlignCenter)

        # scroll_widget = QScrollArea()
        # scroll_widget.setWidget(central_widget)
        # scroll_widget.setWidgetResizable(False)
        # scroll_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        # scroll_widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        # scroll_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # view = QGraphicsView()
        # scene = QGraphicsScene()
        # view.setScene(scene)
        # view.viewport().setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents)
        # view.viewport().grabGesture(Qt.GestureType.PinchGesture)
        # proxy = scene.addWidget(PageWidget())
        notebook = NotebookWidget()
        notebook.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCentralWidget(notebook)
