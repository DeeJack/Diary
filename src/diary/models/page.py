"""
Represents a Page inside a Notebook
"""

import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast, override

from diary.config import settings

from .elements import Image, Stroke, Text
from .page_element import PageElement


@dataclass
class Page:
    """Represents a Page inside a Notebook"""

    def __init__(
        self,
        elements: list[PageElement] | None = None,
        created_at: float | None = None,
        page_id: str | None = None,
        metadata: dict[str, object] | None = None,
        streak_lvl: int = 0,
    ):
        self.elements: list[PageElement] = elements if elements is not None else []
        self.created_at: float = created_at or time.time()
        self.page_id: str = page_id or uuid.uuid4().hex
        self.metadata: dict[str, object] = metadata if metadata is not None else {}
        self.streak_lvl: int = streak_lvl

    def get_creation_date(self) -> datetime:
        """Returns the creation date as datetime.datetime"""
        return datetime.fromtimestamp(self.created_at)

    @property
    def strokes(self) -> list[Stroke]:
        """Legacy property for backward compatibility - returns only stroke elements"""
        return [element for element in self.elements if isinstance(element, Stroke)]

    def add_element(self, element: PageElement) -> None:
        """Add a new element to the page"""
        self.elements.append(element)

    def remove_element(self, element: PageElement) -> None:
        """Remove an element from the page"""
        if element in self.elements:
            self.elements.remove(element)

    def clear_elements(self) -> None:
        """Clear all elements from the page"""
        self.elements.clear()

    @override
    def __str__(self) -> str:
        return f"Page(Elements={len(self.elements)}; Created at={self.created_at}; Page ID={self.page_id}; Metadata={self.metadata})"

    @override
    def __eq__(self, other: object):
        if not isinstance(other, Page):
            return False
        return self.page_id == other.page_id

    def to_dict(self) -> dict[str, Any]:
        """Transforms the object to dict"""
        return {
            settings.SERIALIZATION_KEYS.ELEMENTS.value: [
                element.to_dict() for element in self.elements
            ],
            settings.SERIALIZATION_KEYS.ELEMENT_ID.value: self.page_id,
            settings.SERIALIZATION_KEYS.CREATED_AT.value: self.created_at,
            settings.SERIALIZATION_KEYS.METADATA.value: self.metadata,
            settings.SERIALIZATION_KEYS.STREAK_LVL.value: self.streak_lvl,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]):
        """Builds the object from dict"""
        elements: list[PageElement] = []

        for element in cast(
            list[dict[str, str]], data[settings.SERIALIZATION_KEYS.ELEMENTS.value]
        ):
            if (
                element[settings.SERIALIZATION_KEYS.ELEMENT_TYPE.value]
                == settings.SERIALIZATION_KEYS.TYPE_STROKE.value
            ):
                elements.append(Stroke.from_dict(element))
            elif (
                element[settings.SERIALIZATION_KEYS.ELEMENT_TYPE.value]
                == settings.SERIALIZATION_KEYS.TYPE_IMAGE.value
            ):
                elements.append(Image.from_dict(element))
            elif (
                element[settings.SERIALIZATION_KEYS.ELEMENT_TYPE.value]
                == settings.SERIALIZATION_KEYS.TYPE_TEXT.value
            ):
                elements.append(Text.from_dict(element))

        return cls(
            elements,
            data[settings.SERIALIZATION_KEYS.CREATED_AT.value],
            data[settings.SERIALIZATION_KEYS.ELEMENT_ID.value],
            data[settings.SERIALIZATION_KEYS.METADATA.value],
            data.get(settings.SERIALIZATION_KEYS.STREAK_LVL.value, 0),
        )
