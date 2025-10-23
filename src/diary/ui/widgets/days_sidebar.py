"""The sidebar with the Diary entry for easy navigation"""

from datetime import datetime

from PyQt6.QtWidgets import QDockWidget, QWidget, QListWidget, QListWidgetItem
from PyQt6.QtCore import Qt, pyqtSlot

from diary.ui.widgets.notebook_widget import NotebookWidget


class DaysSidebar(QDockWidget):
    """QDockWidget as sidebar for navigation between Diary entries"""

    def __init__(self, parent: QWidget | None, notebook_widget: NotebookWidget):
        super().__init__("Entries", parent)
        self.notebook_widget: NotebookWidget = notebook_widget

        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.entry_list = QListWidget()
        self.populate_entry_list()
        self.setWidget(self.entry_list)
        self.entry_list.itemClicked.connect(self.on_entry_selected)

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

    @pyqtSlot(QListWidgetItem)
    def on_entry_selected(self, item):
        """When an entry has been selected, scroll to that page"""
        # Retrieve the page index we stored
        page_index = item.data(Qt.ItemDataRole.UserRole)
        if page_index is not None:
            self.notebook_widget.scroll_to_page(page_index)
