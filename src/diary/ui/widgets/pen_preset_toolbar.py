"""Toolbar with quick pen presets for drawing."""

from dataclasses import dataclass

from PyQt6 import QtCore
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import QButtonGroup, QToolBar, QToolButton, QWidget


@dataclass(slots=True, frozen=True)
class PenPreset:
    """Represents a pen preset configuration."""

    name: str
    color: QColor
    width: float
    icon: str = "✏"


class PenPresetToolbar(QToolBar):
    """Fixed toolbar showing pen presets on the left side."""

    preset_selected: pyqtSignal = pyqtSignal(PenPreset)

    def __init__(
        self, parent: QWidget | None = None, presets: list[PenPreset] | None = None
    ) -> None:
        super().__init__("PenPresets", parent)
        self.setMovable(True)
        self.setFloatable(True)
        self.setOrientation(Qt.Orientation.Vertical)
        self.setAllowedAreas(Qt.ToolBarArea.AllToolBarAreas)
        self.setStyleSheet("color: white;")
        self.setIconSize(QtCore.QSize(18, 18))

        self._button_group: QButtonGroup = QButtonGroup(self)
        self._button_group.setExclusive(True)
        self._buttons: list[QToolButton] = []

        for preset in presets or self._default_presets():
            self.add_preset(preset)

    def add_preset(self, preset: PenPreset) -> None:
        """Add a preset button to the toolbar."""
        button = QToolButton()
        button.setText(preset.icon)
        button.setFont(QFont("Times New Roman", 14))
        button.setAutoRaise(True)
        button.setCheckable(True)
        button.setFixedSize(36, 36)
        button.setStyleSheet(self._button_style(preset))
        button.setToolTip(f"{preset.name} ({preset.width:g}px)")
        self._button_group.addButton(button)
        self._buttons.append(button)
        _ = button.clicked.connect(lambda: self.preset_selected.emit(preset))
        _ = self.addWidget(button)

    def _button_style(self, preset: PenPreset) -> str:
        base = preset.color
        background = base.lighter(150)
        border = base.darker(140)
        luminance = (
            0.2126 * base.redF() + 0.7152 * base.greenF() + 0.0722 * base.blueF()
        )
        text_color = "#111111" if luminance > 0.6 else "#f7f7f7"
        return f"""
            QToolButton {{
                background-color: {background.name()};
                color: {text_color};
                border: 1px solid {border.name()};
                border-radius: 12px;
            }}
            QToolButton:checked {{
                background-color: {base.name()};
                border: 2px solid #ffffff;
                color: {text_color};
                font-weight: bold;
            }}
            QToolButton:hover {{
                background-color: {base.lighter(165).name()};
            }}
        """

    def _default_presets(self) -> list[PenPreset]:
        """Default presets for initial release."""
        return [
            PenPreset("Black 1px", QColor("black"), 1.0, "✏"),
            PenPreset("Green 2px", QColor("#1e8f4f"), 2.0, "✏"),
            PenPreset("Title Red 4px", QColor("#b51f1f"), 4.0, "✏"),
        ]
