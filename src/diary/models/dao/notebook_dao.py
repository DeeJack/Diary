from pathlib import Path
import json

from diary.models.notebook import Notebook


class NotebookDAO:
    def save(self, notebook: Notebook, filepath: Path):
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(notebook, f, indent=2)

    def load(self, filepath: Path):
        if not filepath.exists():
            raise ValueError(f"Notebook: {filepath} does not exists")

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
