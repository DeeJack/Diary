"""Methods to save and load the Notebook"""

from pathlib import Path
import json
from typing import Any, Callable, override
import logging

from diary.models.notebook import Notebook
from diary.models.page import Page
from diary.models.stroke import Stroke
from diary.models.point import Point
from diary.models.page_element import PageElement
from diary.models.image import Image
from diary.models.voice_memo import VoiceMemo
from diary.utils import encryption


class NotebookDAO:
    """Contains methods to save and load the Notebook"""

    @staticmethod
    def save(
        notebook: Notebook,
        filepath: Path,
        password: encryption.SecureBuffer,
        salt: bytes,
        progress: Callable[[int, int], None] | None = None,
    ) -> None:
        """Saves the encrypted Notebook using the derived password"""
        notebook_json = json.dumps(notebook, indent=2, cls=MyEncoder)
        logging.getLogger("NotebookDAO").debug("Encrypting and saving the notebook")
        encryption.SecureEncryption.encrypt_json_to_file(
            notebook_json, filepath, password, salt, progress
        )

    @staticmethod
    def save_unencrypted(
        notebook: Notebook,
        filepath: Path,
    ) -> None:
        """Save notebook to unencrypted JSON file (for testing only)"""
        logging.getLogger("NotebookDAO").debug("Num pages: %d", len(notebook.pages))
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(notebook, f, indent=2, cls=MyEncoder)

    @staticmethod
    def load(
        filepath: Path,
        key_buffer: encryption.SecureBuffer,
        progress: Callable[[int, int], None] | None = None,
    ) -> Notebook:
        """Loads the Notebook using the derived key, or returns an empty one"""
        if not filepath.exists():
            logging.getLogger("NotebookDAO").debug(
                "Notebook does not exists, returning a new notebook"
            )
            return Notebook(pages=[Page()])

        logging.getLogger("NotebookDAO").debug("Notebook exists, decrypting")
        notebook_str = NotebookDAO.load_unencrypted(
            Path("data/notebook_encrypted.json")
        )
        # notebook_str = encryption.SecureEncryption.decrypt_file_to_json_with_key(
        #     filepath, key_buffer, progress
        # )
        logging.getLogger("NotebookDAO").debug("Decryption completed successfully!")
        # return NotebookDAO.to_notebook(json.loads(notebook_str))  # pyright: ignore[reportAny]
        return notebook_str  # pyright: ignore[reportAny]

    @staticmethod
    def load_unencrypted(
        filepath: Path,
    ) -> Notebook:
        """Load notebook from unencrypted JSON file (for testing only)"""
        if not filepath.exists():
            return Notebook(pages=[Page()])

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)  # pyright: ignore[reportAny]
            return NotebookDAO.to_notebook(data)  # pyright: ignore[reportAny]

    @staticmethod
    def to_notebook(data: dict[str, Any]) -> Notebook:
        """Converts a dict to Notebook object"""
        pages = []
        if "pages" in data and isinstance(data["pages"], list):
            for page_data in data["pages"]:
                if isinstance(page_data, dict):
                    page = NotebookDAO.to_page(page_data)
                    pages.append(page)

        metadata = data.get("metadata", {}) if isinstance(data, dict) else {}
        return Notebook(pages=pages, metadata=metadata)

    @staticmethod
    def to_page(page_data: dict[str, Any]) -> Page:
        """Converts dict to Page object"""
        elements = []

        # Handle new elements format
        if "elements" in page_data and isinstance(page_data["elements"], list):
            for element_data in page_data["elements"]:
                if isinstance(element_data, dict):
                    element = NotebookDAO.to_element(element_data)
                    if element:
                        elements.append(element)

        return Page(
            elements=elements,
            created_at=page_data.get("created_at"),
            metadata=page_data.get("metadata", {}),
            page_id=page_data.get("page_id"),
        )

    @staticmethod
    def to_element(element_data: dict[str, Any]) -> PageElement | None:
        """Converts dict to PageElement object based on element_type"""
        element_type = element_data.get("element_type", "stroke")

        if element_type == "stroke":
            return Stroke.from_dict(element_data)
        elif element_type == "image":
            return Image.from_dict(element_data)
        elif element_type == "voice_memo":
            return VoiceMemo.from_dict(element_data)

        return None

    @staticmethod
    def to_stroke(stroke_data: dict[str, Any]) -> Stroke:
        """Converts dict to Stroke object (legacy method for backward compatibility)"""
        points = []
        if "points" in stroke_data and isinstance(stroke_data["points"], list):
            for point_data in stroke_data["points"]:
                if isinstance(point_data, dict):
                    point = NotebookDAO.to_point(point_data)
                    points.append(point)

        return Stroke(
            points=points,
            color=stroke_data.get("color", "black"),
            size=stroke_data.get(
                "thickness", 1
            ),  # Note: stroke uses "thickness" but constructor param is "size"
            tool=stroke_data.get("tool", "pen"),
        )

    @staticmethod
    def to_point(point_data: dict[str, Any]) -> Point:
        """Converts dict to Point object"""
        return Point(
            x=point_data.get("x", 0.0),
            y=point_data.get("y", 0.0),
            pressure=point_data.get("pressure", 1.0),
        )


class MyEncoder(json.JSONEncoder):
    """Encodes an object to JSON"""

    @override
    def default(self, o: Any) -> Any:
        # Handle PageElement serialization using their to_dict method
        if isinstance(o, PageElement):
            return o.to_dict()
        elif hasattr(o, "__dict__"):
            return o.__dict__
        return super().default(o)
