"""The sidebar with the Diary entry for easy navigation"""

from datetime import datetime
from typing import Any, cast

from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QAction, QShowEvent
from PyQt6.QtWidgets import QDockWidget, QListWidget, QListWidgetItem, QWidget

from diary.ui.widgets.notebook_widget import NotebookWidget


class DaysSidebar(QDockWidget):
    """QDockWidget as sidebar for navigation between Diary entries"""

    _populated: bool = False

    def __init__(self, parent: QWidget | None, notebook_widget: NotebookWidget):
        super().__init__("", parent)
        self.notebook_widget: NotebookWidget = notebook_widget
        self._populated = False

        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.entry_list: QListWidget = QListWidget()
        # Don't populate here - defer until sidebar is shown
        self._style_entry_list()
        self.setWidget(self.entry_list)
        _ = self.entry_list.itemClicked.connect(self.on_entry_selected)

    def showEvent(self, event: QShowEvent | None) -> None:
        """Populate the list lazily when first shown"""
        if not self._populated:
            self.populate_entry_list()
            self._populated = True
        super().showEvent(event)

    def populate_entry_list(self):
        """Fill the list with the diary entries"""
        self.entry_list.clear()
        for i, page in enumerate(self.notebook_widget.notebook.pages):
            date = datetime.fromtimestamp(page.created_at)
            date_str = date.strftime(
                "%A, %B %d, %Y"
            )  # e.g., "Friday, October 24, 2025"
            item = QListWidgetItem(date_str)
            item.setData(Qt.ItemDataRole.UserRole, i)
            self.entry_list.addItem(item)

    def create_toggle_action(self):
        """Create action to open/close the sidebar"""
        sidebar_action = cast(QAction, self.toggleViewAction())
        sidebar_action.setText("Toggle Entry List")
        sidebar_action.setShortcut("Ctrl+E")
        return sidebar_action

    @pyqtSlot(QListWidgetItem)
    def on_entry_selected(self, item: Any):
        """When an entry has been selected, scroll to that page"""
        # Retrieve the page index we stored
        page_index = cast(int | None, item.data(Qt.ItemDataRole.UserRole))
        if page_index is not None:
            self.notebook_widget.scroll_to_page(page_index)

    def _style_entry_list(self):
        """Applies QSS for a modern look to the entry list."""
        style_sheet = """
            QListWidget {
                background-color: #2B2B2B;
                border: none;
                color: #FFFFFF;
                font-size: 14px;
            }

            QListWidget::item {
                padding: 12px 8px;
                border-bottom: 1px solid #3c3c3c;
            }

            QListWidget::item:hover {
                background-color: #3c3f41;
            }

            QListWidget::item:selected {
                background-color: #0078D7;
                color: #FFFFFF;
                border-left: 3px solid #33A1FF;
            }
        """
        self.entry_list.setStyleSheet(style_sheet)
