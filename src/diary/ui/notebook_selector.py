"""Select a notebook in the UI"""

from typing import cast

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QInputDialog, QLabel, QPushButton, QVBoxLayout, QWidget

from diary.models import Notebook, Page
from diary.ui.widgets.save_manager import pyqtSignal
from diary.ui.widgets.settings_sidebar import QHBoxLayout


class NotebookSelector(QWidget):
    """Select a notebook from the list of available notebooks"""

    notebook_selected: pyqtSignal = pyqtSignal(Notebook)
    list_changed: pyqtSignal = pyqtSignal()

    def __init__(self, notebooks: list[Notebook], parent: QWidget | None):
        super().__init__()
        layout = QVBoxLayout()
        layout.setContentsMargins(200, 50, 200, 50)
        layout.setSpacing(15)

        label = QLabel("Select Notebook:", self)
        label.setFont(QFont("Ubuntu", 18, QFont.Weight.Bold))
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("color: #e9ecef; margin-bottom: 20px;")
        layout.addWidget(label)
        self.setLayout(layout)

        for widget in self._create_notebook_objects(notebooks):
            layout.addWidget(widget)
        layout.addWidget(self._new_notebook_obj(notebooks))
        layout.addStretch()

    def _create_notebook_obj(self, notebook: Notebook, index: int) -> QPushButton:
        button = QPushButton()
        name = notebook.metadata["name"] if "name" in notebook.metadata else index
        button.setText(f"Notebook {name}")
        button.setFont(QFont("Ubuntu", 16))
        button.setMinimumHeight(50)
        button.setStyleSheet("""
            QPushButton {
                background-color: #343a40;
                border: 2px solid #495057;
                border-radius: 8px;
                padding: 12px;
                text-align: left;
                color: #f8f9fa;
            }
            QPushButton:hover {
                background-color: #495057;
                border-color: #6c757d;
            }
            QPushButton:pressed {
                background-color: #6c757d;
            }
        """)
        _ = button.clicked.connect(lambda: self.notebook_selected.emit(notebook))
        return button

    def _get_new_notebook_name(self) -> str:
        name, ok = QInputDialog.getText(self.parentWidget(), "New notebook", "Name")
        if not ok:
            return ""
        return name

    def _new_notebook_obj(self, notebooks: list[Notebook]) -> QWidget:
        notebook = Notebook(pages=[Page()], metadata={"name": ""})
        new_obj = self._create_notebook_obj(notebook, 0)
        new_obj.setText("+ Create New Notebook")
        new_obj.setStyleSheet("""
            QPushButton {
                background-color: #1e3a5f;
                border: 2px dashed #4a90b8;
                border-radius: 8px;
                padding: 12px;
                text-align: center;
                color: #a8d8ea;
            }
            QPushButton:hover {
                background-color: #2e4a6f;
                border-color: #5aa0c8;
            }
        """)

        def _create_new_notebook():
            name = self._get_new_notebook_name()
            if not name:
                return
            notebook.metadata["name"] = name
            notebooks.append(notebook)
            self.notebook_selected.emit(notebook)

        new_obj.clicked.disconnect()
        _ = new_obj.clicked.connect(_create_new_notebook)
        return new_obj

    def _create_delete_btn(
        self, notebook: Notebook, notebooks: list[Notebook], container: QWidget
    ) -> QPushButton:
        delete_btn = QPushButton()
        delete_btn.setText("🗑️")
        delete_btn.setFont(QFont("Ubuntu", 24))
        delete_btn.setFixedWidth(40)
        delete_btn.setMinimumHeight(50)

        def _on_delete():
            notebooks.remove(notebook)
            cast(QVBoxLayout, self.layout()).removeWidget(container)
            self.list_changed.emit()

        _ = delete_btn.clicked.connect(_on_delete)
        self.update()
        return delete_btn

    def _create_rename_btn(
        self, notebook: Notebook, notebook_btn: QPushButton
    ) -> QPushButton:
        rename_btn = QPushButton()
        rename_btn.setText("📝")
        rename_btn.setFont(QFont("Ubuntu", 24))
        rename_btn.setFixedWidth(40)
        rename_btn.setMinimumHeight(50)

        def _on_rename():
            result, ok = QInputDialog.getText(self.parentWidget(), "Rename", "New name")
            if not ok:
                return
            notebook.metadata["name"] = result
            notebook_btn.setText(f"Notebook {result}")
            self.list_changed.emit()

        _ = rename_btn.clicked.connect(_on_rename)
        self.update()
        return rename_btn

    def _create_notebook_objects(self, notebooks: list[Notebook]) -> list[QWidget]:
        notebook_widgets: list[QWidget] = []
        for index, notebook in enumerate(notebooks):
            container = QWidget()
            hlayout = QHBoxLayout(container)
            notebook_btn = self._create_notebook_obj(notebook, index)
            hlayout.addWidget(notebook_btn)
            hlayout.addWidget(self._create_delete_btn(notebook, notebooks, container))
            hlayout.addWidget(self._create_rename_btn(notebook, notebook_btn))

            notebook_widgets.append(container)
        return notebook_widgets
