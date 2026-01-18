"""The sidebar with the Diary entry for easy navigation"""

from collections import defaultdict
from datetime import date, datetime
from typing import Any, cast

from PyQt6.QtCore import QDate, QRect, Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QAction, QBrush, QColor, QPainter, QShowEvent
from PyQt6.QtWidgets import (
    QCalendarWidget,
    QDockWidget,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from diary.config import settings
from diary.ui.widgets.notebook_widget import NotebookWidget
from diary.ui.widgets.search_widget import SearchWidget
from diary.utils.encryption import SecureBuffer


class DiaryCalendarWidget(QCalendarWidget):
    """Custom calendar widget that shows red dots on days with diary entries"""

    def __init__(self, notebook_widget: NotebookWidget, parent: QWidget | None = None):
        super().__init__(parent)
        self.notebook_widget = notebook_widget
        self.entry_dates: dict[date, list[int]] = defaultdict(list)
        self._build_entry_dates()

    def _build_entry_dates(self):
        """Build mapping of dates to page indices"""
        self.entry_dates.clear()
        for i, page in enumerate(self.notebook_widget.notebook.pages):
            page_date = datetime.fromtimestamp(page.created_at).date()
            self.entry_dates[page_date].append(i)

    def refresh_entries(self):
        """Refresh the entry dates mapping and repaint"""
        self._build_entry_dates()
        self.updateCells()

    def paintCell(self, painter: QPainter | None, rect: QRect, date: QDate) -> None:
        """Override to draw red dots on days with entries"""
        if painter is None:
            return

        super().paintCell(painter, rect, date)

        py_date = date.toPyDate()
        if py_date in self.entry_dates:
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(QBrush(QColor("#E53935")))
            painter.setPen(Qt.PenStyle.NoPen)

            dot_radius = 3
            dot_x = rect.center().x()
            dot_y = rect.bottom() - dot_radius - 2
            painter.drawEllipse(
                dot_x - dot_radius, dot_y - dot_radius, dot_radius * 2, dot_radius * 2
            )
            painter.restore()


class DaysSidebar(QDockWidget):
    """QDockWidget as sidebar for navigation between Diary entries"""

    _populated: bool = False

    # Signal to navigate to a search result
    navigate_to_element: pyqtSignal = pyqtSignal(
        str, str, str
    )  # notebook_id, page_id, element_id

    def __init__(
        self,
        parent: QWidget | None,
        notebook_widget: NotebookWidget,
        key_buffer: SecureBuffer,
        salt: bytes,
    ):
        super().__init__("Navigation", parent)
        self.notebook_widget = notebook_widget
        self._populated = False

        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )

        # Main container widget
        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Search widget (top)
        self.search_widget: SearchWidget | None = None
        if settings.SEARCH_ENABLED:
            self.search_widget = SearchWidget(
                key_buffer, salt, self.notebook_widget.notebook.notebook_id, self
            )
            _ = self.search_widget.result_selected.connect(
                self._on_search_result_selected
            )
            main_layout.addWidget(self.search_widget)
        else:
            search_disabled_label = QLabel("Search disabled in settings")
            search_disabled_label.setStyleSheet("color: #888888; font-size: 11px;")
            main_layout.addWidget(search_disabled_label)

        # Create splitter for entry list and calendar
        self.splitter = QSplitter(Qt.Orientation.Vertical)

        # Entry list (top)
        self.entry_list = QListWidget()
        self._style_entry_list()
        _ = self.entry_list.itemClicked.connect(self.on_entry_selected)

        # Calendar (bottom)
        self.calendar = DiaryCalendarWidget(notebook_widget, self)
        self._style_calendar()
        _ = self.calendar.clicked.connect(self._on_calendar_date_clicked)
        _ = self.notebook_widget.current_page_changed.connect(self._on_page_changed)

        self.splitter.addWidget(self.entry_list)
        self.splitter.addWidget(self.calendar)

        # Set initial sizes (entry list gets more space)
        self.splitter.setSizes([300, 200])

        main_layout.addWidget(self.splitter, stretch=1)

        self.setWidget(container)
        self.setMinimumWidth(300)

    def showEvent(self, a0: QShowEvent | None) -> None:
        """Populate the list lazily when first shown"""
        if not self._populated:
            self.populate_entry_list()
            self.calendar.refresh_entries()
            self._select_current_page_date()
            self._populated = True
        super().showEvent(a0)

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
        sidebar_action.setText("Toggle Navigation")
        sidebar_action.setShortcut("Ctrl+E")
        return sidebar_action

    @pyqtSlot(QListWidgetItem)
    def on_entry_selected(self, item: Any):
        """When an entry has been selected, scroll to that page"""
        page_index = cast(int | None, item.data(Qt.ItemDataRole.UserRole))
        if page_index is not None:
            self.notebook_widget.scroll_to_page(page_index)

    def _on_calendar_date_clicked(self, qdate: QDate):
        """Navigate to first page for the clicked date"""
        py_date = qdate.toPyDate()
        page_indices = self.calendar.entry_dates.get(py_date)
        if page_indices:
            self.notebook_widget.scroll_to_page(page_indices[0])

    def _on_page_changed(self, current_page: int, _total: int):
        """Update calendar selection when page changes"""
        if current_page < 0 or current_page >= len(self.notebook_widget.notebook.pages):
            return
        page = self.notebook_widget.notebook.pages[current_page]
        page_date = datetime.fromtimestamp(page.created_at).date()
        qdate = QDate(page_date.year, page_date.month, page_date.day)
        self.calendar.setSelectedDate(qdate)

    def _select_current_page_date(self):
        """Select the date of the current page in the calendar"""
        current_idx = self.notebook_widget._get_current_page_index()
        if 0 <= current_idx < len(self.notebook_widget.notebook.pages):
            page = self.notebook_widget.notebook.pages[current_idx]
            page_date = datetime.fromtimestamp(page.created_at).date()
            qdate = QDate(page_date.year, page_date.month, page_date.day)
            self.calendar.setSelectedDate(qdate)

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

    def _style_calendar(self):
        """Apply dark theme styling to the calendar"""
        style_sheet = """
            QCalendarWidget {
                background-color: #2B2B2B;
                color: #FFFFFF;
            }
            QCalendarWidget QToolButton {
                color: #FFFFFF;
                background-color: #3c3c3c;
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
                margin: 2px;
            }
            QCalendarWidget QToolButton:hover {
                background-color: #4a4a4a;
            }
            QCalendarWidget QMenu {
                background-color: #2B2B2B;
                color: #FFFFFF;
            }
            QCalendarWidget QSpinBox {
                background-color: #3c3c3c;
                color: #FFFFFF;
                border: none;
                border-radius: 4px;
                padding: 2px;
            }
            QCalendarWidget QAbstractItemView:enabled {
                background-color: #2B2B2B;
                color: #FFFFFF;
                selection-background-color: #0078D7;
                selection-color: #FFFFFF;
            }
            QCalendarWidget QAbstractItemView:disabled {
                color: #666666;
            }
            QCalendarWidget QWidget#qt_calendar_navigationbar {
                background-color: #2B2B2B;
            }
        """
        self.calendar.setStyleSheet(style_sheet)

    def _on_search_result_selected(
        self, notebook_id: str, page_id: str, element_id: str
    ) -> None:
        """Handle search result selection - navigate to the page."""
        # Find the page index by page_id
        for i, page in enumerate(self.notebook_widget.notebook.pages):
            if page.page_id == page_id:
                self.notebook_widget.scroll_to_page(i)
                # Emit signal for element highlighting
                self.navigate_to_element.emit(notebook_id, page_id, element_id)
                break

    def focus_search(self) -> None:
        """Focus the search input."""
        if self.search_widget is None:
            return
        self.show()
        self.search_widget.focus_search()

    def close_search_index(self) -> None:
        """Close the search index when closing the sidebar."""
        if self.search_widget is None:
            return
        self.search_widget.close_index()
