"""Represents the toolbar on the bottom of the screen"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QColorDialog,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QToolBar,
    QWidget,
)

from diary.config import settings
from diary.ui.widgets.tool_selector import Tool


class BottomToolbar(QToolBar):
    """The toolbar at the bottom of the page"""

    tool_changed: pyqtSignal = pyqtSignal(Tool)
    thickness_changed: pyqtSignal = pyqtSignal(float)
    color_changed: pyqtSignal = pyqtSignal(QColor)

    def __init__(self, parent: QWidget | None = None):
        super().__init__("BottomToolbar", parent)
        self.setMovable(False)
        self.setAutoFillBackground(False)
        self.setStyleSheet("color: white")

        self.pen_btn: QPushButton = create_button("🖊️")
        _ = self.pen_btn.clicked.connect(
            lambda: self._button_clicked(self.pen_btn, Tool.PEN)
        )

        self.eraser_btn: QPushButton = create_button("⌫")
        _ = self.eraser_btn.clicked.connect(
            lambda: self._button_clicked(self.eraser_btn, Tool.ERASER)
        )

        self.text_btn: QPushButton = create_button("💬")
        _ = self.text_btn.clicked.connect(
            lambda: self._button_clicked(self.text_btn, Tool.TEXT)
        )

        self.drag_btn: QPushButton = create_button("🤚")
        _ = self.drag_btn.clicked.connect(
            lambda: self._button_clicked(self.drag_btn, Tool.DRAG)
        )

        self.image_btn: QPushButton = create_button("🖼️")
        _ = self.image_btn.clicked.connect(
            lambda: self._button_clicked(self.image_btn, Tool.IMAGE)
        )

        self.selection_btn: QPushButton = create_button("🎯")
        _ = self.selection_btn.clicked.connect(
            lambda: self._button_clicked(self.selection_btn, Tool.SELECTION)
        )

        thickness_lbl = QLabel()
        thickness_lbl.setFont(QFont("Times New Roman", 12))
        thickness_lbl.setText("Thickness:")
        self.thickness_slider: QSlider = create_thickness_slider()
        _ = self.thickness_slider.valueChanged.connect(
            lambda: self.thickness_changed.emit(self.thickness_slider.value())
        )

        self.color_dialog: QColorDialog = QColorDialog()

        color_btn = QPushButton()
        color_btn.setText("Color")
        _ = color_btn.clicked.connect(self.color_dialog.show)
        _ = self.color_dialog.colorSelected.connect(
            lambda: self.color_changed.emit(self.color_dialog.currentColor())
        )

        self.buttons: list[QPushButton] = [
            self.pen_btn,
            self.eraser_btn,
            self.text_btn,
            self.drag_btn,
            self.image_btn,
            self.selection_btn,
        ]

        self._add_filling_spacer()
        for button in self.buttons:
            _ = self.addWidget(button)
            self._add_spacer(10)
        self._add_spacer(30)
        _ = self.addWidget(thickness_lbl)
        self._add_spacer(10)
        _ = self.addWidget(self.thickness_slider)
        self._add_spacer(30)
        _ = self.addWidget(color_btn)
        self._add_filling_spacer()

        self._button_clicked(self.pen_btn, Tool.PEN)

    def _button_clicked(self, button: QPushButton, tool: Tool):
        """When a button is clicked"""
        for other in self.buttons:
            other.setDisabled(False)
            other.setStyleSheet("")  # Reset to default style
        button.setDisabled(True)
        button.setStyleSheet("""
            QPushButton:disabled {
                background-color: #007acc;
                color: white;
                border: 2px solid #005a9e;
                font-weight: bold;
            }
        """)
        self.tool_changed.emit(tool)

    def _add_filling_spacer(self):
        """Add a spacer that fills the entire space available"""
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        _ = self.addWidget(spacer)

    def _add_spacer(self, width: float):
        """Add a spacer with a fixed width"""
        spacer = QWidget()
        spacer.setFixedWidth(int(width))
        _ = self.addWidget(spacer)


def create_button(text: str) -> QPushButton:
    """Creates a button with custom parameters and styling"""
    new_button: QPushButton = QPushButton()
    new_button.setText(text)
    new_button.setFont(QFont("Times New Roman", 14))
    new_button.setFixedWidth(40)
    new_button.setStyleSheet("""
        QPushButton {
            color: white;
        }
        QPushButton:hover {
            background-color: #777;
        }
        QPushButton:pressed {
            background-color: #555;
        }
    """)
    return new_button


def create_thickness_slider() -> QSlider:
    """Creates the thickness slider"""
    thickness_slider: QSlider = QSlider(Qt.Orientation.Horizontal)
    thickness_slider.setMinimum(1)
    thickness_slider.setMaximum(10)
    thickness_slider.setTickInterval(1)
    thickness_slider.setFixedWidth(80)
    thickness_slider.setFixedHeight(30)
    thickness_slider.setValue(int(settings.CURRENT_WIDTH))
    return thickness_slider
