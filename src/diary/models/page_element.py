"""Abstract base class for all page elements"""

from abc import ABC, abstractmethod
from typing import Any, override
import uuid
from diary.models.point import Point


class PageElement(ABC):
    """Abstract base class for all elements that can be placed on a page"""

    def __init__(self, element_type: str, element_id: str | None = None):
        self.element_type: str = element_type
        self.element_id: str | None = element_id or uuid.uuid4().hex

    @abstractmethod
    def intersects(self, pos: Point, radius: float) -> bool:
        """Check if this element intersects with a circle at the given position and radius"""
        pass

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Serialize this element to a dictionary for JSON storage"""
        pass

    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict[str, Any]) -> "PageElement":
        """Deserialize this element from a dictionary loaded from JSON"""
        pass

    @override
    def __eq__(self, other: object, /) -> bool:
        if not isinstance(other, PageElement):
            return False

        # if both have IDs and they match, elements are equal
        if hasattr(self, "element_id") and hasattr(other, "element_id"):
            if self.element_id and other.element_id:
                return self.element_id == other.element_id

        return NotImplemented
