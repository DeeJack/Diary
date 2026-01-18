"""
Index Manager - Coordinates indexing lifecycle for the search system.

Manages OCR workers and index updates, handles change detection,
and provides signals for UI progress updates.
"""

import logging
import time

from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal

from diary.models import Notebook
from diary.models.elements import Stroke, Text
from diary.models.elements.voice_memo import VoiceMemo
from diary.models.page import Page
from diary.search.ocr_worker import OCRWorker, TextIndexWorker
from diary.search.search_index import SearchEntry, SearchIndex
from diary.search.stroke_rasterizer import StrokeGroup, StrokeRasterizer
from diary.utils.encryption import SecureBuffer


class IndexManager(QObject):
    """
    Manages the search index lifecycle.

    Coordinates OCR workers, handles change detection,
    and provides progress signals for UI feedback.
    """

    # Signals
    indexing_started: pyqtSignal = pyqtSignal()
    indexing_progress: pyqtSignal = pyqtSignal(int, int, str)  # current, total, message
    indexing_complete: pyqtSignal = pyqtSignal(int)  # number of items indexed
    indexing_error: pyqtSignal = pyqtSignal(str)

    def __init__(self, key_buffer: SecureBuffer, salt: bytes):
        """
        Initialize the index manager.

        Args:
            key_buffer: Encryption key for the search index
            salt: Salt used for key derivation
        """
        super().__init__()
        self.logger = logging.getLogger("IndexManager")
        self._index = SearchIndex(key_buffer, salt)
        self._is_indexing: bool = False
        self._pending_pages: list[tuple[Page, str]] = []  # (page, notebook_id)

        # Threading
        self._ocr_thread: QThread | None = None
        self._ocr_worker: OCRWorker | None = None
        self._text_thread: QThread | None = None
        self._text_worker: TextIndexWorker | None = None

        # Track current indexing state
        self._current_notebook_id: str | None = None
        self._total_pages: int = 0
        self._processed_pages: int = 0
        self._indexed_count: int = 0
        self._pending_ocr_entries: list[SearchEntry] = []

    @property
    def is_indexing(self) -> bool:
        """Check if indexing is currently in progress."""
        return self._is_indexing

    def open_index(self) -> None:
        """Open the search index."""
        self._index.open()

    def close_index(self) -> None:
        """Close and save the search index."""
        self._cancel_workers()
        self._index.close()
        # Release the OCR reader to prevent shutdown crashes
        OCRWorker.release_reader()

    def _cancel_workers(self) -> None:
        """Cancel any running workers and wait for threads to finish."""
        self._is_indexing = False

        if self._ocr_worker:
            self._ocr_worker.cancel()
        if self._text_worker:
            self._text_worker.cancel()

        # Wait for OCR thread to finish
        if self._ocr_thread is not None:
            if self._ocr_thread.isRunning():
                self._ocr_thread.quit()
                if not self._ocr_thread.wait(5000):
                    self.logger.warning("OCR thread did not stop in time")
            self._ocr_thread.deleteLater()
            self._ocr_thread = None
            self._ocr_worker = None

        # Wait for text thread to finish
        if self._text_thread is not None:
            if self._text_thread.isRunning():
                self._text_thread.quit()
                if not self._text_thread.wait(5000):
                    self.logger.warning("Text thread did not stop in time")
            self._text_thread.deleteLater()
            self._text_thread = None
            self._text_worker = None

    def index_notebooks(self, notebooks: list[Notebook]) -> None:
        """
        Index all pages in the given notebooks.

        Uses change detection to only re-index modified content.

        Args:
            notebooks: List of notebooks to index
        """
        if self._is_indexing:
            self.logger.debug("Already indexing, skipping request")
            return

        self._is_indexing = True
        self._indexed_count = 0
        self.indexing_started.emit()

        # Collect all pages that need indexing
        self._pending_pages = []
        for notebook in notebooks:
            for page in notebook.pages:
                self._pending_pages.append((page, notebook.notebook_id))

        self._total_pages = len(self._pending_pages)
        self._processed_pages = 0

        if not self._pending_pages:
            self._finish_indexing()
            return

        # Start processing first page
        self._process_next_page()

    def index_page_async(self, page: Page, notebook_id: str) -> None:
        """
        Index a single page asynchronously.

        Args:
            page: Page to index
            notebook_id: ID of the notebook containing the page
        """
        if self._is_indexing:
            # Queue the page for later
            self._pending_pages.append((page, notebook_id))
            return

        self._is_indexing = True
        self._indexed_count = 0
        self._pending_pages = [(page, notebook_id)]
        self._total_pages = 1
        self._processed_pages = 0
        self.indexing_started.emit()
        self._process_next_page()

    def _process_next_page(self) -> None:
        """Process the next page in the queue."""
        if not self._pending_pages:
            self._finish_indexing()
            return

        page, notebook_id = self._pending_pages.pop(0)
        self._current_notebook_id = notebook_id
        self._process_page(page, notebook_id)

    def _process_page(self, page: Page, notebook_id: str) -> None:
        """
        Process a single page for indexing.

        Indexes text elements immediately and queues strokes for OCR.

        Args:
            page: Page to process
            notebook_id: ID of the notebook containing the page
        """
        self.indexing_progress.emit(
            self._processed_pages,
            self._total_pages,
            f"Processing page {self._processed_pages + 1}/{self._total_pages}",
        )

        # Collect text entries that need indexing
        text_entries: list[tuple[str, str, str]] = []
        strokes: list[Stroke] = []

        for element in page.elements:
            element_id = element.element_id

            if isinstance(element, Text):
                # Check if content changed
                current_hash = SearchIndex.compute_content_hash(element.text)
                existing_hash = self._index.get_content_hash(element_id)

                if existing_hash != current_hash:
                    text_entries.append((element_id, "text", element.text))

            elif isinstance(element, VoiceMemo) and element.transcript:
                # Check if transcript changed
                current_hash = SearchIndex.compute_content_hash(element.transcript)
                existing_hash = self._index.get_content_hash(element_id)

                if existing_hash != current_hash:
                    text_entries.append((element_id, "voice_memo", element.transcript))

            elif isinstance(element, Stroke):
                strokes.append(element)

        # Remove deleted text/voice entries from index
        current_non_stroke_ids = {
            e.element_id for e in page.elements if isinstance(e, (Text, VoiceMemo))
        }
        indexed_non_stroke_ids = self._index.get_indexed_element_ids(
            page.page_id, element_types=["text", "voice_memo"]
        )
        deleted_non_stroke_ids = indexed_non_stroke_ids - current_non_stroke_ids
        for element_id in deleted_non_stroke_ids:
            self._index.remove_entry(element_id)

        # Build stroke groups and detect changes
        stroke_groups = StrokeRasterizer.group_strokes_by_proximity(strokes)
        current_group_ids: set[str] = set()
        stroke_groups_to_ocr: list[StrokeGroup] = []
        for group in stroke_groups:
            group_id = StrokeRasterizer.compute_group_id(group)
            current_group_ids.add(group_id)
            current_hash = StrokeRasterizer.compute_group_hash(group)
            existing_hash = self._index.get_content_hash(group_id)
            if existing_hash != current_hash:
                stroke_groups_to_ocr.append(group)

        # Remove deleted stroke group entries
        indexed_stroke_ids = self._index.get_indexed_element_ids(
            page.page_id, element_types=["stroke"]
        )
        deleted_stroke_ids = indexed_stroke_ids - current_group_ids
        for element_id in deleted_stroke_ids:
            self._index.remove_entry(element_id)

        # Index text entries immediately (fast)
        for element_id, element_type, text in text_entries:
            entry = SearchEntry(
                element_id=element_id,
                page_id=page.page_id,
                notebook_id=notebook_id,
                element_type=element_type,
                text_content=text,
                bounding_box=None,
                content_hash=SearchIndex.compute_content_hash(text),
                last_indexed=time.time(),
            )
            self._index.add_entry(entry)
            self._indexed_count += 1

        # Queue strokes for OCR if any
        if stroke_groups_to_ocr:
            self._start_ocr_worker(stroke_groups_to_ocr, page.page_id, notebook_id)
        else:
            # No OCR needed, move to next page
            self._processed_pages += 1
            self._process_next_page()

    def _start_ocr_worker(
        self, stroke_groups: list[StrokeGroup], page_id: str, notebook_id: str
    ) -> None:
        """Start the OCR worker for a batch of strokes."""
        # Ensure previous thread is fully cleaned up
        if self._ocr_thread is not None:
            if self._ocr_thread.isRunning():
                self.logger.warning("Previous OCR thread still running, waiting...")
                self._ocr_thread.quit()
                self._ocr_thread.wait(5000)
            self._ocr_thread = None
        if self._ocr_worker is not None:
            self._ocr_worker = None

        self._ocr_thread = QThread()
        self._ocr_worker = OCRWorker(stroke_groups, page_id, notebook_id)
        self._ocr_worker.moveToThread(self._ocr_thread)

        # Connect signals
        _ = self._ocr_thread.started.connect(self._ocr_worker.run)
        _ = self._ocr_worker.finished.connect(self._on_ocr_finished)
        _ = self._ocr_worker.error.connect(self._on_ocr_error)
        _ = self._ocr_worker.progress.connect(self._on_ocr_progress)

        # Cleanup connections - quit thread when worker finishes
        _ = self._ocr_worker.finished.connect(self._ocr_thread.quit)
        # Clean up and process next page when thread is fully finished
        _ = self._ocr_thread.finished.connect(self._on_ocr_thread_finished)

        self._ocr_thread.start()

    def _on_ocr_finished(self, entries: list[SearchEntry]) -> None:
        """Handle OCR completion - store entries for later processing."""
        # Store entries to be added after thread cleanup
        self._pending_ocr_entries = entries

    def _on_ocr_error(self, error_msg: str) -> None:
        """Handle OCR error."""
        self.logger.error("OCR error: %s", error_msg)
        self._pending_ocr_entries = []

    def _on_ocr_thread_finished(self) -> None:
        """Handle thread completion - clean up and process next page."""
        # Add pending entries to index
        if hasattr(self, "_pending_ocr_entries"):
            for entry in self._pending_ocr_entries:
                self._index.add_entry(entry)
                self._indexed_count += 1
            self._pending_ocr_entries = []

        self._processed_pages += 1

        # Clean up the old thread objects
        if self._ocr_worker:
            self._ocr_worker.deleteLater()
            self._ocr_worker = None
        if self._ocr_thread:
            self._ocr_thread.deleteLater()
            self._ocr_thread = None

        # Use QTimer to defer processing to next event loop iteration
        # This ensures the thread is fully cleaned up before starting a new one
        QTimer.singleShot(0, self._process_next_page)

    def _on_ocr_progress(self, current: int, total: int, message: str) -> None:
        """Handle OCR progress update."""
        self.indexing_progress.emit(
            self._processed_pages,
            self._total_pages,
            f"Page {self._processed_pages + 1}: {message}",
        )

    def _cleanup_ocr_thread(self) -> None:
        """Clean up the OCR thread."""
        if self._ocr_worker:
            self._ocr_worker.cancel()
            self._ocr_worker.deleteLater()
            self._ocr_worker = None
        if self._ocr_thread:
            if self._ocr_thread.isRunning():
                self._ocr_thread.quit()
                self._ocr_thread.wait(5000)  # Wait up to 5 seconds
            self._ocr_thread.deleteLater()
            self._ocr_thread = None

    def _finish_indexing(self) -> None:
        """Finish the indexing process."""
        self._is_indexing = False
        self._index.close()  # Save to disk
        self._index.open()  # Reopen for queries
        self.logger.info("Indexing complete: %d items indexed", self._indexed_count)
        self.indexing_complete.emit(self._indexed_count)

    def search(
        self,
        query: str,
        element_types: list[str] | None = None,
        notebook_id: str | None = None,
        limit: int = 50,
    ) -> list[SearchEntry]:
        """
        Search the index.

        Args:
            query: Search query
            element_types: Filter by element types
            notebook_id: Filter by notebook ID
            limit: Maximum results

        Returns:
            List of matching SearchEntry objects
        """
        return self._index.search(query, element_types, notebook_id, limit)

    def get_stats(self) -> dict[str, int]:
        """Get index statistics."""
        return self._index.get_stats()

    def rebuild_index(self, notebooks: list[Notebook]) -> None:
        """
        Rebuild the entire search index from scratch.

        Args:
            notebooks: List of notebooks to index
        """
        self.logger.info("Rebuilding search index...")

        # Close and delete existing index
        self._index.close()
        if self._index._index_path.exists():
            self._index._index_path.unlink()

        # Reopen (creates new empty index)
        self._index.open()

        # Index all notebooks
        self.index_notebooks(notebooks)
