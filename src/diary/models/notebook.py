"""
Represents the Notebook model, containing the pages of the Diary
"""

import logging
import uuid
from dataclasses import dataclass
from typing import Any, override

from diary.config import settings
from diary.models.page import Page


@dataclass
class Notebook:
    """Represents the Notebook with its Pages"""

    def __init__(
        self,
        pages: list[Page] | None = None,
        metadata: dict[str, object] | None = None,
        notebook_id: str | None = None,
    ):
        self.pages: list[Page] = pages or []
        self.metadata: dict[str, object] = metadata or {}
        self.notebook_id: str = notebook_id or uuid.uuid4().hex

    def add_page(self, page: Page | None = None, page_idx: int = -1):
        """Adds a new page"""
        page = page or Page()

        # Determine actual insertion position
        actual_idx = page_idx if page_idx >= 0 else len(self.pages)

        # Set streak level based on the page before the insertion point
        if actual_idx > 0 and self.pages:
            # Get the page that will be before this one after insertion
            prev_page = self.pages[actual_idx - 1]
            page.streak_lvl = self._calculate_streak_level(page, prev_page)

        logging.getLogger("Notebook").debug(
            "Created new page with streak lvl: %d", page.streak_lvl
        )
        if page_idx == -1:
            self.pages.append(page)
        else:
            self.pages.insert(page_idx, page)

        # Recalculate streak levels for all pages after the inserted page
        self._update_subsequent_streaks(actual_idx + 1)

    def remove_page(self, page_index: int) -> bool:
        """Remove a page at the specified index. Returns True if successful."""
        if 0 <= page_index < len(self.pages):
            _ = self.pages.pop(page_index)
            logging.getLogger("Notebook").debug("Removed page at index: %d", page_index)
            return True
        return False

    def _calculate_streak_level(self, new_page: Page, last_page: Page) -> int:
        """Calculate the streak level for a new page based on the last page"""
        new_date = new_page.get_creation_date()
        last_date = last_page.get_creation_date()

        day_diff = (new_date.date() - last_date.date()).days

        if day_diff == 0:  # Same day
            return last_page.streak_lvl
        if day_diff == 1:  # Next day (consecutive)
            return last_page.streak_lvl + 1
        return 0  # Streak broken

    def _update_subsequent_streaks(self, start_idx: int) -> None:
        """Update streak levels for all pages starting from start_idx"""
        for i in range(start_idx, len(self.pages)):
            if i > 0:
                prev_page = self.pages[i - 1]
                self.pages[i].streak_lvl = self._calculate_streak_level(
                    self.pages[i], prev_page
                )

    def fix_all_streaks(self) -> None:
        """Recalculate all streak levels for the entire notebook.

        Use this to fix streak levels in an existing notebook where streaks
        may have become incorrect due to date changes or other modifications.
        """
        if not self.pages:
            return

        # First page always starts at 0
        self.pages[0].streak_lvl = 0

        # Recalculate all subsequent pages
        self._update_subsequent_streaks(1)

        logging.getLogger("Notebook").info(
            "Fixed streak levels for %d pages", len(self.pages)
        )

    def update_page_streak(self, page_idx: int) -> None:
        """Update the streak level for a specific page and all subsequent pages.

        Call this after changing a page's date to ensure streak levels are correct.

        Args:
            page_idx: The index of the page whose date was changed
        """
        if page_idx < 0 or page_idx >= len(self.pages):
            return

        # Recalculate the changed page's streak
        if page_idx > 0:
            prev_page = self.pages[page_idx - 1]
            self.pages[page_idx].streak_lvl = self._calculate_streak_level(
                self.pages[page_idx], prev_page
            )
        else:
            self.pages[page_idx].streak_lvl = 0

        # Update all subsequent pages
        self._update_subsequent_streaks(page_idx + 1)

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
            settings.SERIALIZATION_KEYS.NOTEBOOK_ID.value: self.notebook_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]):
        """Builds the object from a dictionary"""
        notebook_id: str = uuid.uuid4().hex
        if hasattr(data, "id"):
            notebook_id = data["id"]

        return cls(
            [
                Page.from_dict(page)
                for page in data[settings.SERIALIZATION_KEYS.PAGES.value]
            ],
            data[settings.SERIALIZATION_KEYS.METADATA.value],
            notebook_id,
        )

    @override
    def __eq__(self, value: object, /) -> bool:
        """Checks equality"""
        if not isinstance(value, Notebook):
            return False

        return self.notebook_id == value.notebook_id
