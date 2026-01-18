# Search Feature Implementation - Change Log

## New Files Created

### `src/diary/search/` module (6 files)

| File | Description |
|------|-------------|
| `__init__.py` | Module exports for SearchEngine, SearchIndex, SearchResult, IndexManager, StrokeRasterizer, etc. |
| `stroke_rasterizer.py` | BoundingBox dataclass, StrokeGroup dataclass, StrokeRasterizer class with methods for grouping strokes by proximity and rendering them to PIL images |
| `search_index.py` | SearchEntry dataclass, SearchIndex class with encrypted SQLite FTS5 storage, JSON-based persistence, CRUD operations for entries |
| `ocr_worker.py` | OCRWorker (QObject) for background OCR using EasyOCR, TextIndexWorker for indexing text elements, class-level reader caching with release_reader() method |
| `index_manager.py` | IndexManager (QObject) coordinating indexing lifecycle, manages OCR/text workers, emits progress signals, handles thread cleanup |
| `search_engine.py` | SearchFilter enum, SearchResult dataclass, SearchEngine class with query conversion to FTS5 syntax, result highlighting |

### `src/diary/ui/widgets/search_widget.py`

- SearchWidget (QWidget) with search input, filter dropdown (All/Text/Handwriting/Voice), results list, debounced search, result_selected signal

### `tests/search/` (4 files)

| File | Tests |
|------|-------|
| `__init__.py` | Empty module init |
| `test_stroke_rasterizer.py` | 15 tests for BoundingBox and StrokeRasterizer |
| `test_search_index.py` | 16 tests for SearchIndex and content hashing |
| `test_search_engine.py` | 16 tests for SearchEngine, query conversion, highlighting |

---

## Modified Files

### `src/diary/config.py`

- Added 4 new settings before `SERIALIZATION_KEYS`:
  - `SEARCH_INDEX_PATH: Path = DATA_DIR_PATH / "search_index.db.enc"`
  - `OCR_LANGUAGE: str = "en"`
  - `OCR_STROKE_GROUPING_GAP: float = 50.0`
  - `SEARCH_DEBOUNCE_MS: int = 300`

### `src/diary/ui/widgets/days_sidebar.py`

- Added imports: `pyqtSignal`, `QVBoxLayout`, `SearchWidget`, `SecureBuffer`
- Modified `DaysSidebar.__init__()`:
  - Added `key_buffer: SecureBuffer` and `salt: bytes` parameters
  - Created container widget with QVBoxLayout
  - Added SearchWidget at top of sidebar
  - Added `navigate_to_element` signal
  - Changed minimum width from 280 to 300
- Added 3 new methods at end of class:
  - `_on_search_result_selected(notebook_id, page_id, element_id)` - handles navigation to search results
  - `focus_search()` - shows sidebar and focuses search input
  - `close_search_index()` - closes the search engine on the widget

### `src/diary/ui/main_window.py`

- Added imports: `QShortcut`, `QKeySequence`, `IndexManager`
- Added `index_manager: IndexManager` instance variable declaration
- Modified `_on_notebooks_loaded()`:
  - Creates IndexManager with key_buffer and salt
  - Opens the index
  - Connects save_completed signal to trigger background indexing
  - Starts initial background indexing of all notebooks
- Modified `_open_notebook()`:
  - Added `key_buffer` and `salt` parameters to DaysSidebar constructor
  - Added Ctrl+F keyboard shortcut that calls `_focus_search()`
- Modified `_on_close_save_completed()`:
  - Closes index_manager first, then sidebar search index
  - Processes Qt events to allow deleteLater() to complete
- Added 2 new methods:
  - `_focus_search()` - focuses the search input in the sidebar
  - `_trigger_background_indexing(save_success, notebooks)` - triggers indexing after successful save

### `pyproject.toml`

- Added 3 dependencies to `[project.dependencies]`:
  - `"easyocr (>=1.7.0,<2.0.0)"`
  - `"pillow (>=10.0.0,<11.0.0)"`
  - `"numpy (>=1.26.0,<2.0.0)"`
- Added mypy override section for missing type stubs:
  ```toml
  [[tool.mypy.overrides]]
  module = ["easyocr.*", "numpy.*", "PIL.*"]
  ignore_missing_imports = true
  ```

---

## Bug Fixes (Threading/Shutdown Crashes)

### `src/diary/search/index_manager.py`

- Added `QTimer` import
- Added `_pending_ocr_entries: list[SearchEntry] = []` instance variable
- Rewrote `_start_ocr_worker()`:
  - Added safety check to ensure previous thread is fully stopped before creating new one
  - Waits up to 5 seconds for previous thread if still running
- Split OCR completion handling into two methods:
  - `_on_ocr_finished(entries)` - now only stores entries in `_pending_ocr_entries`, does not process next page
  - `_on_ocr_thread_finished()` - new method called when QThread.finished emits, handles cleanup and uses QTimer.singleShot(0) to defer next page processing
- Rewrote `_cancel_workers()`:
  - Sets `_is_indexing = False`
  - Properly waits for threads with timeout
  - Calls `deleteLater()` on thread and worker objects
  - Sets thread/worker references to None
- Modified `close_index()`:
  - Calls `OCRWorker.release_reader()` after canceling workers to free PyTorch resources

### `src/diary/search/ocr_worker.py`

- Added `release_reader()` class method:
  - Sets `_reader = None` to release EasyOCR model
  - Calls `gc.collect()` to force garbage collection of PyTorch resources
  - Prevents shutdown crashes from orphaned PyTorch threads

### `src/diary/search/search_index.py`

- Removed unused imports: `tempfile`, `time`, `Path`
- Fixed `open()` method:
  - Only creates schema if no existing index file exists
  - Loads from disk first if file exists, then schema is created during load
- Rewrote `_load_from_disk()`:
  - Changed from SQL dump to JSON format
  - Creates schema, then restores entries from JSON
  - FTS5 virtual tables don't work properly with iterdump()
- Rewrote `_save_to_disk()`:
  - Changed from SQL dump to JSON format
  - Exports all entries as JSON with version field
  - Properly handles FTS5 data preservation
