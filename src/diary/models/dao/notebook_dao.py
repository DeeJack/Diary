from pathlib import Path
import json
from typing import Any, cast

from diary.models.notebook import Notebook


class NotebookDAO:
    @staticmethod
    def save(notebook: Notebook, filepath: Path):
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(notebook, f, indent=2, cls=MyEncoder)

    @staticmethod
    def load(filepath: Path) -> Notebook:
        if not filepath.exists():
            raise ValueError(f"Notebook: {filepath} does not exists")

        with open(filepath, "r", encoding="utf-8") as f:
            data = NotebookDAO.to_notebook(json.load(f))
        return data

    @staticmethod
    def to_notebook(obj: Any) -> Notebook:  # pyright: ignore[reportExplicitAny, reportAny]
        return cast(Notebook, obj)


class MyEncoder(json.JSONEncoder):
    def default(self, o):
        return o.__dict__
