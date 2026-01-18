"""
Search Widget - UI component for searching the diary.

Provides a search bar with filter options and results list.
"""

import logging

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from diary.config import settings
from diary.search.search_engine import SearchEngine, SearchFilter, SearchResult
from diary.utils.encryption import SecureBuffer


class SearchWidget(QWidget):
    """
    Widget for searching the diary.

    Contains a search input, filter dropdown, and results list.
    Emits signals when the user selects a search result.
    """

    # Emitted when user selects a result: (notebook_id, page_id, element_id)
    result_selected: pyqtSignal = pyqtSignal(str, str, str)

    def __init__(
        self,
        key_buffer: SecureBuffer,
        salt: bytes,
        notebook_id: str | None = None,
        parent: QWidget | None = None,
    ):
        """
        Initialize the search widget.

        Args:
            key_buffer: Encryption key for the search index
            salt: Salt used for key derivation
            parent: Parent widget
        """
        super().__init__(parent)
        self.logger: logging.Logger = logging.getLogger("SearchWidget")
        self._search_engine: SearchEngine = SearchEngine(key_buffer, salt)
        self._search_engine.open()
        self._notebook_id: str | None = notebook_id

        # Debounce timer
        self._debounce_timer: QTimer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(settings.SEARCH_DEBOUNCE_MS)
        _ = self._debounce_timer.timeout.connect(self._execute_search)

        # Current results for navigation
        self._current_results: list[SearchResult] = []

        self._setup_ui()
        self._style_widget()

    def _setup_ui(self) -> None:
        """Set up the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Search input row
        search_row = QHBoxLayout()
        search_row.setSpacing(4)

        # Search input
        self._search_input: QLineEdit = QLineEdit()
        self._search_input.setPlaceholderText("Search diary...")
        self._search_input.setClearButtonEnabled(True)
        _ = self._search_input.textChanged.connect(self._on_text_changed)
        _ = self._search_input.returnPressed.connect(self._execute_search)
        search_row.addWidget(self._search_input, stretch=1)

        # Filter dropdown
        self._filter_combo: QComboBox = QComboBox()
        self._filter_combo.addItem("All", SearchFilter.ALL)
        self._filter_combo.addItem("Text", SearchFilter.TEXT_ONLY)
        self._filter_combo.addItem("Handwriting", SearchFilter.HANDWRITING_ONLY)
        self._filter_combo.addItem("Voice", SearchFilter.VOICE_ONLY)
        self._filter_combo.setFixedWidth(100)
        _ = self._filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        search_row.addWidget(self._filter_combo)

        layout.addLayout(search_row)

        # Progress bar (hidden by default)
        self._progress_bar: QProgressBar = QProgressBar()
        self._progress_bar.setMaximumHeight(4)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.hide()
        layout.addWidget(self._progress_bar)

        # Results count label
        self._results_label: QLabel = QLabel("")
        self._results_label.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(self._results_label)

        # Results list
        self._results_list: QListWidget = QListWidget()
        _ = self._results_list.itemClicked.connect(self._on_result_clicked)
        _ = self._results_list.itemDoubleClicked.connect(self._on_result_double_clicked)
        layout.addWidget(self._results_list)

    def _style_widget(self) -> None:
        """Apply dark theme styling."""
        self.setStyleSheet("""
            QLineEdit {
                background-color: #3c3c3c;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 6px 8px;
                color: #FFFFFF;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #0078D7;
            }
            QComboBox {
                background-color: #3c3c3c;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 4px 8px;
                color: #FFFFFF;
                font-size: 12px;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #FFFFFF;
                margin-right: 6px;
            }
            QComboBox QAbstractItemView {
                background-color: #3c3c3c;
                border: 1px solid #555555;
                color: #FFFFFF;
                selection-background-color: #0078D7;
            }
            QListWidget {
                background-color: #2B2B2B;
                border: none;
                color: #FFFFFF;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #3c3c3c;
            }
            QListWidget::item:hover {
                background-color: #3c3f41;
            }
            QListWidget::item:selected {
                background-color: #0078D7;
            }
            QProgressBar {
                background-color: #3c3c3c;
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background-color: #0078D7;
                border-radius: 2px;
            }
        """)

    def _on_text_changed(self, text: str) -> None:
        """Handle search input text change with debouncing."""
        self._debounce_timer.stop()
        if text.strip():
            self._debounce_timer.start()
        else:
            self._clear_results()

    def _on_filter_changed(self, index: int) -> None:
        """Handle filter selection change."""
        if self._search_input.text().strip():
            self._execute_search()

    def _execute_search(self) -> None:
        """Execute the search query."""
        query = self._search_input.text().strip()
        if not query:
            self._clear_results()
            return

        filter_type: SearchFilter | None = self._filter_combo.currentData()
        if filter_type is None:
            filter_type = SearchFilter.ALL

        self.logger.debug("Executing search: %s (filter: %s)", query, filter_type)

        try:
            results = self._search_engine.search(
                query,
                filter_type,
                notebook_id=self._notebook_id,
                limit=settings.SEARCH_MAX_RESULTS,
            )
            self._display_results(results)
        except Exception as e:
            self.logger.error("Search failed: %s", e)
            self._results_label.setText("Search error")
            self._results_list.clear()

    def _display_results(self, results: list[SearchResult]) -> None:
        """Display search results in the list."""
        self._current_results = results
        self._results_list.clear()

        if not results:
            self._results_label.setText("No results found")
            return

        self._results_label.setText(
            f"{len(results)} result{'s' if len(results) != 1 else ''}"
        )

        for result in results:
            item = QListWidgetItem()

            # Format the display text
            type_icon = self._get_type_icon(result.element_type)
            # Remove markdown bold markers for display
            snippet = result.snippet.replace("**", "")
            display_text = f"{type_icon} {snippet}"

            item.setText(display_text)
            item.setToolTip(result.matched_text)

            # Store result data for navigation
            item.setData(Qt.ItemDataRole.UserRole, result)

            self._results_list.addItem(item)

    def _get_type_icon(self, element_type: str) -> str:
        """Get an icon character for the element type."""
        icons = {
            "text": "T",
            "stroke": "S",
            "voice_memo": "V",
        }
        return f"[{icons.get(element_type, '?')}]"

    def _clear_results(self) -> None:
        """Clear the results list."""
        self._current_results = []
        self._results_list.clear()
        self._results_label.setText("")

    def _on_result_clicked(self, item: QListWidgetItem) -> None:
        """Handle single click on a result (for preview)."""
        # Could be used for preview functionality in the future
        pass

    def _on_result_double_clicked(self, item: QListWidgetItem) -> None:
        """Handle double click on a result (navigate to page)."""
        result = item.data(Qt.ItemDataRole.UserRole)
        if result and isinstance(result, SearchResult):
            self.result_selected.emit(
                result.notebook_id, result.page_id, result.element_id
            )

    def focus_search(self) -> None:
        """Focus the search input and select all text."""
        self._search_input.setFocus()
        self._search_input.selectAll()

    def set_indexing_progress(self, current: int, total: int, message: str) -> None:
        """Update the indexing progress indicator."""
        if total > 0:
            self._progress_bar.setMaximum(total)
            self._progress_bar.setValue(current)
            self._progress_bar.show()
        else:
            self._progress_bar.hide()

    def set_indexing_complete(self) -> None:
        """Hide the indexing progress indicator."""
        self._progress_bar.hide()

    def close_index(self) -> None:
        """Close the search engine."""
        self._search_engine.close(save=False)

    def reload_index(self) -> None:
        """Reload the search index from disk and rerun the current query."""
        self._search_engine.close(save=False)
        self._search_engine.open()
        if self._search_input.text().strip():
            self._execute_search()
