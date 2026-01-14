"""Represents the toolbar on the bottom of the screen"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QTabletEvent
from PyQt6.QtWidgets import (
    QColorDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSlider,
    QToolBar,
    QWidget,
)

from diary.config import settings
from diary.ui.input import InputType
from diary.ui.widgets.tool_selector import Tool


class ToolButton(QPushButton):
    """Custom button that detects whether it was clicked with pen/tablet or mouse/touch"""

    clicked_with_device = pyqtSignal(str)  # Emits "tablet" or "mouse"

    def __init__(self, text: str = ""):
        super().__init__(text)
        self.setFont(QFont("Times New Roman", 14))
        self.setFixedWidth(40)
        self.setFixedHeight(30)
        self.setStyleSheet(
            """
            QPushButton {
                color: white;
            }
            QPushButton:hover {
                background-color: #777;
            }
            QPushButton:pressed {
                background-color: #555;
            }
        """
        )
        self._tablet_event_active = False

    def tabletEvent(self, event: QTabletEvent | None) -> None:
        """Handle tablet/pen events"""
        if event and event.type() in (
            QTabletEvent.Type.TabletPress,
            QTabletEvent.Type.TabletMove,
            QTabletEvent.Type.TabletRelease,
        ):
            if event.type() == QTabletEvent.Type.TabletPress:
                self._tablet_event_active = True
                self.clicked_with_device.emit("tablet")
                self.click()
            event.accept()
        else:
            super().tabletEvent(event)

    def mousePressEvent(self, event) -> None:
        """Handle mouse/touch events"""
        # Check if this is a synthesized mouse event from a tablet event
        if not self._tablet_event_active:
            self.clicked_with_device.emit("mouse")
        self._tablet_event_active = False
        super().mousePressEvent(event)


class BottomToolbar(QToolBar):
    """The toolbar at the bottom of the page"""

    tool_changed: pyqtSignal = pyqtSignal(Tool)
    tool_changed_with_device: pyqtSignal = pyqtSignal(
        Tool, str
    )  # Tool, device ("tablet" or "mouse")
    thickness_changed: pyqtSignal = pyqtSignal(float)
    color_changed: pyqtSignal = pyqtSignal(QColor)

    def __init__(self, parent: QWidget | None = None):
        super().__init__("BottomToolbar", parent)
        self.setMovable(False)
        self.setAutoFillBackground(False)
        self.setStyleSheet("color: white")

        self.pen_btn: ToolButton = create_tool_button("🖊️")
        _ = self.pen_btn.clicked_with_device.connect(
            lambda device: self._button_clicked(self.pen_btn, Tool.PEN, device)
        )

        self.eraser_btn: ToolButton = create_tool_button("⌫")
        _ = self.eraser_btn.clicked_with_device.connect(
            lambda device: self._button_clicked(self.eraser_btn, Tool.ERASER, device)
        )

        self.text_btn: ToolButton = create_tool_button("💬")
        _ = self.text_btn.clicked_with_device.connect(
            lambda device: self._button_clicked(self.text_btn, Tool.TEXT, device)
        )

        self.drag_btn: ToolButton = create_tool_button("🤚")
        _ = self.drag_btn.clicked_with_device.connect(
            lambda device: self._button_clicked(self.drag_btn, Tool.DRAG, device)
        )

        self.image_btn: ToolButton = create_tool_button("🖼️")
        _ = self.image_btn.clicked_with_device.connect(
            lambda device: self._button_clicked(self.image_btn, Tool.IMAGE, device)
        )

        self.selection_btn: ToolButton = create_tool_button("🎯")
        _ = self.selection_btn.clicked_with_device.connect(
            lambda device: self._button_clicked(
                self.selection_btn, Tool.SELECTION, device
            )
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

        text_size_lbl = QLabel()
        text_size_lbl.setFont(QFont("Times New Roman", 12))
        text_size_lbl.setText("Text Size (px):")
        self.text_size_input: QLineEdit = QLineEdit()
        self.text_size_input.setFixedWidth(60)
        self.text_size_input.setFont(QFont("Times New Roman", 12))
        self.text_size_input.setText("12")
        self.text_size_input.setPlaceholderText("12")
        _ = self.text_size_input.textChanged.connect(self._on_text_size_changed)

        self.info_label: QLabel = QLabel()
        self.info_label.setFont(QFont("Times New Roman", 12))

        # Mouse mode toggle button
        self.mouse_toggle_btn: QPushButton = QPushButton("🖱️")
        self.mouse_toggle_btn.setFont(QFont("Times New Roman", 14))
        self.mouse_toggle_btn.setFixedWidth(40)
        self.mouse_toggle_btn.setFixedHeight(30)
        self.mouse_toggle_btn.setCheckable(True)
        self.mouse_toggle_btn.setChecked(settings.MOUSE_ENABLED)
        self.mouse_toggle_btn.setToolTip("Mouse mode: when disabled, mouse/touch acts as drag hand only")
        self._update_mouse_toggle_style()
        _ = self.mouse_toggle_btn.clicked.connect(self._toggle_mouse_mode)

        self.buttons: list[ToolButton] = [
            self.pen_btn,
            self.eraser_btn,
            self.text_btn,
            self.drag_btn,
            self.image_btn,
            self.selection_btn,
        ]

        _ = self.addWidget(self.info_label)
        self._add_filling_spacer()
        for button in self.buttons:
            _ = self.addWidget(button)
            self._add_spacer(10)

        # Add separator and mouse toggle
        self._add_spacer(10)
        _ = self.addWidget(self.mouse_toggle_btn)
        self._add_spacer(30)
        _ = self.addWidget(thickness_lbl)
        self._add_spacer(10)
        _ = self.addWidget(self.thickness_slider)
        self._add_spacer(30)
        _ = self.addWidget(color_btn)
        self._add_spacer(30)
        _ = self.addWidget(text_size_lbl)
        self._add_spacer(10)
        _ = self.addWidget(self.text_size_input)
        self._add_filling_spacer()

        self._button_clicked(self.pen_btn, Tool.PEN, "tablet")

    def _button_clicked(self, button: ToolButton, tool: Tool, device: str = "tablet"):
        """When a button is clicked"""
        for other in self.buttons:
            other.setDisabled(False)
            other.setStyleSheet("")  # Reset to default style
        button.setDisabled(True)
        button.setStyleSheet(
            """
            QPushButton:disabled {
                background-color: #007acc;
                color: white;
                font-weight: bold;
            }
        """
        )
        self.tool_changed.emit(tool)  # Keep backward compatibility
        self.tool_changed_with_device.emit(tool, device)

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

    def set_info_text(self, text: str):
        """Set the text for the info label"""
        self.info_label.setText(text)

    def clear_text(self):
        """Clear the text from the info label"""
        self.info_label.setText("")

    def _on_text_size_changed(self, text: str):
        """Handle text size input changes"""
        try:
            size = int(text)
            if size > 0:
                settings.TEXT_SIZE_PX = size
        except ValueError:
            pass  # Ignore invalid input

    def _toggle_mouse_mode(self):
        """Toggle mouse mode on/off"""
        settings.MOUSE_ENABLED = self.mouse_toggle_btn.isChecked()
        self._update_mouse_toggle_style()

    def _update_mouse_toggle_style(self):
        """Update the mouse toggle button style based on state"""
        if settings.MOUSE_ENABLED:
            self.mouse_toggle_btn.setStyleSheet(
                """
                QPushButton {
                    background-color: #007acc;
                    color: white;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #005a9e;
                }
            """
            )
        else:
            self.mouse_toggle_btn.setStyleSheet(
                """
                QPushButton {
                    background-color: #444;
                    color: #888;
                }
                QPushButton:hover {
                    background-color: #555;
                }
            """
            )


def create_button(text: str) -> QPushButton:
    """Creates a button with custom parameters and styling (legacy, use create_tool_button for tool buttons)"""
    new_button: QPushButton = QPushButton()
    new_button.setText(text)
    new_button.setFont(QFont("Times New Roman", 14))
    new_button.setFixedWidth(40)
    new_button.setFixedHeight(30)
    new_button.setStyleSheet(
        """
        QPushButton {
            color: white;
        }
        QPushButton:hover {
            background-color: #777;
        }
        QPushButton:pressed {
            background-color: #555;
        }
    """
    )
    return new_button


def create_tool_button(text: str) -> ToolButton:
    """Creates a tool button that can detect tablet vs mouse input"""
    return ToolButton(text)


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
