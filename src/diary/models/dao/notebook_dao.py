from pathlib import Path
import json
from typing import Any, override

from diary.models.notebook import Notebook
from diary.models.page import Page
from diary.models.stroke import Stroke
from diary.models.point import Point


class NotebookDAO:
    @staticmethod
    def save(notebook: Notebook, filepath: Path) -> None:
        # to_save = notebook.copy()
        # for page in to_save.pages.copy():  # Iterate over the copy
        #     if len(page.strokes) == 0:
        #         to_save.pages.remove(page)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(notebook, f, indent=2, cls=MyEncoder)

    @staticmethod
    def load(filepath: Path) -> Notebook:
        if not filepath.exists():
            return Notebook(pages=[Page()])

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            return NotebookDAO.to_notebook(data)

    @staticmethod
    def to_notebook(data: dict[str, Any]) -> Notebook:
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
        strokes = []
        if "strokes" in page_data and isinstance(page_data["strokes"], list):
            for stroke_data in page_data["strokes"]:
                if isinstance(stroke_data, dict):
                    stroke = NotebookDAO.to_stroke(stroke_data)
                    strokes.append(stroke)

        return Page(
            strokes=strokes,
            created_at=page_data.get("created_at"),
            metadata=page_data.get("metadata", {}),
            page_id=page_data.get("page_id"),
        )

    @staticmethod
    def to_stroke(stroke_data: dict[str, Any]) -> Stroke:
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
        return Point(
            x=point_data.get("x", 0.0),
            y=point_data.get("y", 0.0),
            pressure=point_data.get("pressure", 1.0),
        )


class MyEncoder(json.JSONEncoder):
    @override
    def default(self, o: Any) -> Any:
        if hasattr(o, "__dict__"):
            return o.__dict__
        return super().default(o)
