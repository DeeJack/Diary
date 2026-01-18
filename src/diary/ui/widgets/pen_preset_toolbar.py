"""Toolbar with quick pen presets for drawing."""

from dataclasses import dataclass

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import QButtonGroup, QLabel, QPushButton, QToolBar


@dataclass(slots=True, frozen=True)
class PenPreset:
    """Represents a pen preset configuration."""

    name: str
    color: QColor
    width: float


class PenPresetToolbar(QToolBar):
    """Fixed toolbar showing pen presets on the left side."""

    preset_selected: pyqtSignal = pyqtSignal(PenPreset)

    def __init__(self, parent=None, presets: list[PenPreset] | None = None) -> None:
        super().__init__("PenPresets", parent)
        self.setMovable(False)
        self.setFloatable(False)
        self.setOrientation(Qt.Orientation.Vertical)
        self.setAllowedAreas(Qt.ToolBarArea.LeftToolBarArea)
        self.setStyleSheet("color: white;")

        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(True)
        self._buttons: list[QPushButton] = []

        title = QLabel("Pens")
        title.setFont(QFont("Times New Roman", 12))
        self.addWidget(title)
        self.addSeparator()

        for preset in presets or self._default_presets():
            self.add_preset(preset)

    def add_preset(self, preset: PenPreset) -> None:
        """Add a preset button to the toolbar."""
        button = QPushButton(preset.name)
        button.setFont(QFont("Times New Roman", 11))
        button.setCheckable(True)
        button.setMinimumWidth(110)
        button.setFixedHeight(32)
        accent = preset.color.name()
        button.setStyleSheet(
            f"""
            QPushButton {{
                background-color: #3a3a3a;
                color: white;
                border: 2px solid transparent;
                border-left: 6px solid {accent};
                padding-left: 6px;
                text-align: left;
            }}
            QPushButton:checked {{
                background-color: #4a4a4a;
                border: 2px solid #007acc;
                border-left: 6px solid {accent};
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #4a4a4a;
            }}
            """
        )
        button.setToolTip(f"{preset.name} ({preset.width:g}px)")
        self._button_group.addButton(button)
        self._buttons.append(button)
        _ = button.clicked.connect(lambda: self.preset_selected.emit(preset))
        self.addWidget(button)

    def _default_presets(self) -> list[PenPreset]:
        """Default presets for initial release."""
        return [
            PenPreset("Black 1px", QColor("black"), 1.0),
            PenPreset("Green 2px", QColor("#1e8f4f"), 2.0),
            PenPreset("Title Red 4px", QColor("#b51f1f"), 4.0),
        ]
