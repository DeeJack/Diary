"""
Represents the Notebook model, containing the pages of the Diary
"""

from dataclasses import dataclass
from typing import Any, override

from diary.config import settings
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

    def to_dict(self):
        return {
            settings.SERIALIZATION_KEYS.PAGES.value: [
                page.to_dict() for page in self.pages
            ],
            settings.SERIALIZATION_KEYS.METADATA.value: self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]):
        return cls(
            [
                Page.from_dict(page)
                for page in data[settings.SERIALIZATION_KEYS.PAGES.value]
            ],
            data[settings.SERIALIZATION_KEYS.METADATA.value],
        )
