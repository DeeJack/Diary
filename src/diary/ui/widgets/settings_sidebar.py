"""Sidebar with all the settings"""

import logging
from typing import Callable, cast

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QDockWidget,
    QListWidget,
    QListWidgetItem,
    QWidget,
)

from diary.config import settings


class SettingsSidebar(QDockWidget):
    """Sidebar with all the settings"""

    last_index: int = 0

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.items: dict[int, Callable[[], None]] = {}
        self.entry_list: QListWidget = QListWidget()
        self._add_items()
        self.setWidget(self.entry_list)
        _ = self.entry_list.itemClicked.connect(self.on_item_clicked)
        _ = self.entry_list.itemChanged.connect(self.on_item_changed)

    def _add_items(self):
        mouse_ckb_idx = self._add_checkbox("Mouse enabled")
        self.items[mouse_ckb_idx] = self._toggle_mouse
        touch_ckb_idx = self._add_checkbox("Touch enabled")
        self.items[touch_ckb_idx] = self._toggle_touch

    def _add_checkbox(self, label: str) -> int:
        curr_index = self.last_index
        self.last_index += 1

        item = QListWidgetItem()
        item.setWhatsThis(str(curr_index))
        item.setText(label)
        item.setFlags(
            item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled
        )
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Unchecked)
        self.entry_list.addItem(item)
        return curr_index

    def on_item_clicked(self, item: QListWidgetItem):
        if item.checkState() == Qt.CheckState.Unchecked:
            item.setCheckState(Qt.CheckState.Checked)
        else:
            item.setCheckState(Qt.CheckState.Unchecked)

    def on_item_changed(self, item: QListWidgetItem):
        try:
            self.items[int(item.whatsThis())]()
        except ValueError as e:
            logging.getLogger("Settings").error(
                "WhatsThis not an int? %s, %s", item.whatsThis(), e
            )

    def _toggle_mouse(self):
        settings.MOUSE_ENABLED = not settings.MOUSE_ENABLED

    def _toggle_touch(self):
        settings.TOUCH_ENABLED = not settings.TOUCH_ENABLED

    def create_toggle_action(self):
        """Create action to open/close the sidebar"""
        sidebar_action = cast(QAction, self.toggleViewAction())
        sidebar_action.setText("Toggle Settings")
        sidebar_action.setShortcut("Ctrl+,")
        return sidebar_action
