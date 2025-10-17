from dataclasses import dataclass
from typing import Self, override

from diary.models.page import Page


@dataclass
class Notebook:
    def __init__(
        self, pages: list[Page] | None = None, metadata: dict[str, object] | None = None
    ):
        self.pages: list[Page] = pages or []
        self.metadata: dict[str, object] = metadata or {}

    @override
    def __str__(self) -> str:
        return f"Notebook(Page={self.pages}; Metatada={self.metadata})"

    def copy(self) -> "Notebook":
        return Notebook(self.pages.copy(), metadata=self.metadata.copy())
