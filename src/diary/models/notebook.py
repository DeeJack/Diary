"""
Represents the Notebook model, containing the pages of the Diary
"""

import logging
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

    def add_page(self, page: Page | None = None):
        """Adds a new page"""
        page = page or Page()

        # Set streak level based on previous page
        if self.pages:
            last_page = self.pages[-1]
            page.streak_lvl = self._calculate_streak_level(page, last_page)

        logging.getLogger("Notebook").debug(
            "Created new page with streak lvl: %d", page.streak_lvl
        )
        self.pages.append(page)

    def remove_page(self, page_index: int) -> bool:
        """Remove a page at the specified index. Returns True if successful."""
        if 0 <= page_index < len(self.pages):
            self.pages.pop(page_index)
            logging.getLogger("Notebook").debug("Removed page at index: %d", page_index)
            return True
        return False

    def _calculate_streak_level(self, new_page: Page, last_page: Page) -> int:
        """Calculate the streak level for a new page based on the last page"""
        new_date = new_page.get_creation_date()
        last_date = last_page.get_creation_date()

        # Only calculate streak if pages are in the same month/year
        if new_date.year != last_date.year or new_date.month != last_date.month:
            return 0

        day_diff = new_date.day - last_date.day

        if day_diff == 0:  # Same day
            return last_page.streak_lvl
        if day_diff == 1:  # Next day
            return last_page.streak_lvl + 1
        return 0

    @override
    def __str__(self) -> str:
        return f"Notebook(Page={self.pages}; Metatada={self.metadata})"

    def to_dict(self):
        """Returns the object as a dict[str, dict]"""
        return {
            settings.SERIALIZATION_KEYS.PAGES.value: [
                page.to_dict() for page in self.pages
            ],
            settings.SERIALIZATION_KEYS.METADATA.value: self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]):
        """Builds the object from a dictionary"""
        return cls(
            [
                Page.from_dict(page)
                for page in data[settings.SERIALIZATION_KEYS.PAGES.value]
            ],
            data[settings.SERIALIZATION_KEYS.METADATA.value],
        )

    @override
    def __eq__(self, value: object, /) -> bool:
        """Checks equality"""
        # Todo: introduce an ID check
        if not isinstance(value, Notebook):
            return False

        if len(value.pages) != len(self.pages) or value.metadata != self.metadata:
            return False
        return value.to_dict() == self.to_dict()
