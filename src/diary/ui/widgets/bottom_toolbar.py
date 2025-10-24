"""Represents the toolbar on the bottom of the screen"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QColorDialog,
    QLabel,
    QPushButton,
    QSlider,
    QToolBar,
    QWidget,
    QSizePolicy,
)

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
        self.setStyleSheet("background-color: #4b4d51; margin-bottom: 25px")
        self.setStyleSheet("color: white")

        self.pen_btn: QPushButton = QPushButton()
        self.pen_btn.setText("🖊️")
        self.pen_btn.setFont(QFont("Times New Roman", 14))
        self.pen_btn.setFixedWidth(40)
        _ = self.pen_btn.clicked.connect(lambda: self.tool_changed.emit(Tool.PEN))

        self.eraser_btn: QPushButton = QPushButton()
        self.eraser_btn.setText("⌫")
        self.eraser_btn.setFont(QFont("Times New Roman", 14))
        self.eraser_btn.setFixedWidth(40)
        _ = self.eraser_btn.clicked.connect(lambda: self.tool_changed.emit(Tool.ERASER))

        self.text_btn: QPushButton = QPushButton()
        self.text_btn.setText("💬")
        self.text_btn.setFont(QFont("Times New Roman", 14))
        self.text_btn.setFixedWidth(40)
        _ = self.text_btn.clicked.connect(lambda: self.tool_changed.emit(Tool.TEXT))

        thickness_lbl = QLabel()
        thickness_lbl.setFont(QFont("Times New Roman", 12))
        thickness_lbl.setText("Thickness:")
        self.thickness_slider: QSlider = QSlider(Qt.Orientation.Horizontal)
        self.thickness_slider.setMinimum(1)
        self.thickness_slider.setMaximum(10)
        self.thickness_slider.setTickInterval(1)
        self.thickness_slider.setFixedWidth(80)
        self.thickness_slider.setFixedHeight(30)
        _ = self.thickness_slider.valueChanged.connect(
            lambda: self.thickness_changed.emit(self.thickness_slider.value())
        )

        self.color_dialog: QColorDialog = QColorDialog()

        color_btn = QPushButton()
        color_btn.setText("Color")
        _ = color_btn.clicked.connect(lambda: self.color_dialog.show())
        _ = self.color_dialog.colorSelected.connect(
            lambda: self.color_changed.emit(self.color_dialog.currentColor())
        )

        self._add_filling_spacer()
        _ = self.addWidget(self.pen_btn)
        self._add_spacer(10)
        _ = self.addWidget(self.eraser_btn)
        self._add_spacer(10)
        _ = self.addWidget(self.text_btn)
        self._add_spacer(30)
        _ = self.addWidget(thickness_lbl)
        self._add_spacer(10)
        _ = self.addWidget(self.thickness_slider)
        self._add_spacer(30)
        _ = self.addWidget(color_btn)
        self._add_filling_spacer()

    def _add_filling_spacer(self):
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        _ = self.addWidget(spacer)

    def _add_spacer(self, width: float):
        spacer = QWidget()
        spacer.setFixedWidth(int(width))
        _ = self.addWidget(spacer)
