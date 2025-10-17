"""
Represents the Notebook model, containing the pages of the Diary
"""

from dataclasses import dataclass
from typing import override

from diary.models.page import Page


@dataclass
class Notebook:
    """Represents the Notebook with its Pages"""

    def __init__(
        self, pages: list[Page] | None = None, metadata: dict[str, object] | None = None
    ):
        self.pages: list[Page] = pages or []
        self.metadata: dict[str, object] = metadata or {}

    @override
    def __str__(self) -> str:
        return f"Notebook(Page={self.pages}; Metatada={self.metadata})"
