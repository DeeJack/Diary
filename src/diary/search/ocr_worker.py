"""
Background OCR processing worker using PaddleOCR.

Follows the existing LoadWorker/SaveWorker pattern for threaded operations.
"""

import logging
import time
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal

from diary.config import settings
from diary.search.search_index import SearchEntry, SearchIndex
from diary.search.stroke_rasterizer import StrokeGroup, StrokeRasterizer


class OCRWorker(QObject):
    """
    Worker that runs OCR in a separate thread.

    Processes stroke groups and emits search entries for indexing.
    Uses lazy loading for the OCR reader to avoid blocking startup.
    """

    # Signals
    finished: pyqtSignal = pyqtSignal(list)  # list[SearchEntry]
    error: pyqtSignal = pyqtSignal(str)
    progress: pyqtSignal = pyqtSignal(int, int, str)  # current, total, message

    # Class-level reader cache (shared across instances)
    _reader: Any = None
    _reader_loading: bool = False

    @classmethod
    def release_reader(cls) -> None:
        """
        Release the cached OCR reader to free GPU/CPU resources.

        Should be called during application shutdown to prevent
        crashes from orphaned PyTorch threads.
        """
        if cls._reader is not None:
            logging.getLogger("OCRWorker").debug("Releasing OCR reader")
            cls._reader = None
            # Force garbage collection to clean up PyTorch resources
            import gc

            gc.collect()

    def __init__(
        self,
        stroke_groups: list[StrokeGroup],
        page_id: str,
        notebook_id: str,
    ):
        """
        Initialize the OCR worker.

        Args:
            strokes: List of strokes to OCR
            page_id: ID of the page containing the strokes
            notebook_id: ID of the notebook containing the page
        """
        super().__init__()
        self.stroke_groups = stroke_groups
        self.page_id = page_id
        self.notebook_id = notebook_id
        self._is_cancelled: bool = False
        self.logger = logging.getLogger("OCRWorker")

    @classmethod
    def _get_reader(cls) -> Any:
        """
        Get or create the OCR reader (lazy loading).

        The reader is cached at class level and shared across instances
        to avoid repeated model loading.
        """
        if cls._reader is not None:
            return cls._reader

        if cls._reader_loading:
            # Another instance is loading, wait
            import time

            while cls._reader_loading and cls._reader is None:
                time.sleep(0.1)
            return cls._reader

        cls._reader_loading = True
        try:
            if settings.OCR_ENGINE == "paddle":
                from paddleocr import PaddleOCR

                logging.getLogger("OCRWorker").info(
                    "Loading PaddleOCR model for lang: %s", settings.OCR_PADDLE_LANG
                )
                cls._reader = PaddleOCR(
                    lang=settings.OCR_PADDLE_LANG,
                    use_angle_cls=settings.OCR_USE_ANGLE_CLS,
                    use_gpu=settings.OCR_USE_GPU,
                    show_log=False,
                    det_db_thresh=settings.OCR_DET_DB_THRESH,
                    det_db_box_thresh=settings.OCR_DET_DB_BOX_THRESH,
                    det_db_unclip_ratio=settings.OCR_DET_DB_UNCLIP_RATIO,
                )
                logging.getLogger("OCRWorker").info(
                    "PaddleOCR model loaded successfully"
                )
                return cls._reader
            return None
        except ImportError:
            logging.getLogger("OCRWorker").error("PaddleOCR not installed")
            return None
        except Exception as e:
            logging.getLogger("OCRWorker").error("Failed to load OCR model: %s", e)
            return None
        finally:
            cls._reader_loading = False

    def run(self) -> None:
        """Main work function - processes strokes through OCR."""
        try:
            if self._is_cancelled:
                self.finished.emit([])
                return

            if not self.stroke_groups:
                self.finished.emit([])
                return

            self.progress.emit(0, len(self.stroke_groups), "Rasterizing strokes...")

            rasterized: list[tuple[Any, StrokeGroup]] = []
            for group in self.stroke_groups:
                image = StrokeRasterizer.render_stroke_group(group)
                rasterized.append((image, group))

            if self._is_cancelled:
                self.finished.emit([])
                return

            if not rasterized:
                self.finished.emit([])
                return

            self.progress.emit(0, len(rasterized), "Loading OCR model...")

            # Get OCR reader (if needed)
            reader = None
            if settings.OCR_ENGINE == "paddle":
                reader = self._get_reader()
                if reader is None:
                    self.error.emit("Failed to load OCR model")
                    self.finished.emit([])
                    return

            if self._is_cancelled:
                self.finished.emit([])
                return

            # Process each stroke group
            entries: list[SearchEntry] = []
            for i, (image, group) in enumerate(rasterized):
                if self._is_cancelled:
                    break

                self.progress.emit(
                    i + 1,
                    len(rasterized),
                    f"Processing group {i + 1}/{len(rasterized)}",
                )

                try:
                    if settings.OCR_DEBUG_SAVE_IMAGES:
                        self._save_debug_image(image, group, i)

                    # Run OCR on the image
                    import numpy as np

                    if settings.OCR_ENGINE == "tesseract":
                        text = self._ocr_with_tesseract(image)
                        if text.strip():
                            print(
                                f"OCR results for group {i + 1}/{len(rasterized)}: {text.strip()}"
                            )
                            entry = self._create_entry(group, text.strip())
                            entries.append(entry)
                    else:
                        image_array = np.array(image.convert("RGB"))
                        results = reader.ocr(image_array, cls=settings.OCR_USE_ANGLE_CLS)

                        if results:
                            # Combine all detected text above minimum confidence
                            lines: list[str] = []
                            for block in results:
                                if not isinstance(block, list):
                                    continue
                                for line in block:
                                    if (
                                        isinstance(line, list)
                                        and len(line) >= 2
                                        and isinstance(line[1], (list, tuple))
                                        and line[1]
                                    ):
                                        text = str(line[1][0])
                                        score = (
                                            float(line[1][1])
                                            if len(line[1]) > 1
                                            else 1.0
                                        )
                                        if text and score >= settings.OCR_REC_MIN_SCORE:
                                            lines.append(text)
                            text = " ".join(lines)
                            if text.strip():
                                print(
                                    f"OCR results for group {i + 1}/{len(rasterized)}: {text.strip()}"
                                )
                                entry = self._create_entry(group, text.strip())
                                entries.append(entry)
                                self.logger.debug(
                                    "OCR extracted text from %d strokes: %s",
                                    len(group.strokes),
                                    text[:50] + "..." if len(text) > 50 else text,
                                )
                except Exception as e:
                    self.logger.warning("OCR failed for stroke group: %s", e)
                    continue

            if not self._is_cancelled:
                self.finished.emit(entries)
        except Exception as e:
            self.logger.error("OCR worker error: %s", e)
            self.error.emit(str(e))
            self.finished.emit([])

    def _create_entry(self, group: StrokeGroup, text: str) -> SearchEntry:
        """Create a SearchEntry from an OCR result."""
        import json

        bbox = group.bounding_box
        bounding_box_json = json.dumps(
            {
                "x": bbox.min_x,
                "y": bbox.min_y,
                "w": bbox.width,
                "h": bbox.height,
            }
        )

        element_id = StrokeRasterizer.compute_group_id(group)
        content_hash = StrokeRasterizer.compute_group_hash(group)

        return SearchEntry(
            element_id=element_id,
            page_id=self.page_id,
            notebook_id=self.notebook_id,
            element_type="stroke",
            text_content=text,
            bounding_box=bounding_box_json,
            content_hash=content_hash,
            last_indexed=time.time(),
        )

    def _save_debug_image(self, image: Any, group: StrokeGroup, index: int) -> None:
        """Save the OCR input image for debugging."""
        try:
            output_dir = Path(settings.OCR_DEBUG_IMAGE_DIR)
            output_dir.mkdir(parents=True, exist_ok=True)
            group_id = StrokeRasterizer.compute_group_id(group)
            filename = (
                f"ocr_{self.notebook_id}_{self.page_id}_{index + 1}_{group_id}.png"
            )
            image.save(output_dir / filename)
        except Exception as e:
            self.logger.warning("Failed to save OCR debug image: %s", e)

    def _ocr_with_tesseract(self, image: Any) -> str:
        """Run OCR using Tesseract on the given image."""
        try:
            import pytesseract

            return pytesseract.image_to_string(
                image, lang=settings.OCR_TESSERACT_LANG
            )
        except Exception as e:
            self.logger.warning("Tesseract OCR failed: %s", e)
            return ""

    def cancel(self) -> None:
        """Cancel the OCR operation."""
        self._is_cancelled = True


class TextIndexWorker(QObject):
    """
    Worker that indexes text elements and voice memo transcripts.

    This is much faster than OCR and can run separately.
    """

    finished: pyqtSignal = pyqtSignal(list)  # list[SearchEntry]
    error: pyqtSignal = pyqtSignal(str)

    def __init__(
        self,
        text_entries: list[tuple[str, str, str]],  # (element_id, element_type, text)
        page_id: str,
        notebook_id: str,
    ):
        """
        Initialize the text index worker.

        Args:
            text_entries: List of (element_id, element_type, text) tuples
            page_id: ID of the page containing the elements
            notebook_id: ID of the notebook containing the page
        """
        super().__init__()
        self.text_entries = text_entries
        self.page_id = page_id
        self.notebook_id = notebook_id
        self._is_cancelled: bool = False
        self.logger = logging.getLogger("TextIndexWorker")

    def run(self) -> None:
        """Main work function - creates search entries for text content."""
        try:
            if self._is_cancelled:
                self.finished.emit([])
                return

            entries: list[SearchEntry] = []
            for element_id, element_type, text in self.text_entries:
                if self._is_cancelled:
                    break

                if not text or not text.strip():
                    continue

                entry = SearchEntry(
                    element_id=element_id,
                    page_id=self.page_id,
                    notebook_id=self.notebook_id,
                    element_type=element_type,
                    text_content=text.strip(),
                    bounding_box=None,
                    content_hash=SearchIndex.compute_content_hash(text.strip()),
                    last_indexed=time.time(),
                )
                entries.append(entry)

            if not self._is_cancelled:
                self.finished.emit(entries)
        except Exception as e:
            self.logger.error("Text index worker error: %s", e)
            self.error.emit(str(e))
            self.finished.emit([])

    def cancel(self) -> None:
        """Cancel the operation."""
        self._is_cancelled = True
