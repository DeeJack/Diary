"""A string of text in the page"""

import math
from dataclasses import dataclass
from typing import Any, cast, override

from diary.config import settings
from diary.models.page_element import PageElement
from diary.models.point import Point


@dataclass
class Text(PageElement):
    """Represents a string of text in the page"""

    def __init__(
        self,
        text: str,
        position: Point,
        color: str = "black",
        size_px: float = 20,
        element_id: str | None = None,
    ):
        super().__init__("text", element_id)
        self.text: str = text
        self.position: Point = position
        self.color: str = color
        self.size_px: float = size_px

    @override
    def intersects(self, pos: Point, radius: float) -> bool:
        # TODO: intersect the entire rect of the text, not just the origin!
        distance = math.sqrt(
            (self.position.x - pos.x) ** 2 + (self.position.y - pos.y) ** 2
        )
        if distance <= radius:
            return True
        return False

    @override
    def to_dict(self) -> dict[str, Any]:
        """Serialize this text to a dictionary for JSON storage"""
        return {
            settings.SERIALIZATION_KEYS.ELEMENT_TYPE.value: self.element_type,
            settings.SERIALIZATION_KEYS.ELEMENT_ID.value: self.element_id,
            settings.SERIALIZATION_KEYS.POSITION.value: [
                self.position.x,
                self.position.y,
            ],
            settings.SERIALIZATION_KEYS.COLOR.value: self.color,
            settings.SERIALIZATION_KEYS.TEXT.value: self.text,
            settings.SERIALIZATION_KEYS.SIZE_PX.value: self.size_px,
        }

    @classmethod
    @override
    def from_dict(cls, data: dict[str, Any]) -> "Text":
        """Deserialize this stroke from a dictionary loaded from JSON"""
        position = cast(
            list[float], data.get(settings.SERIALIZATION_KEYS.POSITION.value)
        )
        return cls(
            element_id=data.get(settings.SERIALIZATION_KEYS.ELEMENT_ID.value),
            text=cast(str, data.get(settings.SERIALIZATION_KEYS.TEXT.value, "")),
            position=Point(position[0], position[1]),
            color=cast(str, data.get(settings.SERIALIZATION_KEYS.COLOR.value, "black")),
            size_px=float(data.get(settings.SERIALIZATION_KEYS.SIZE_PX.value, 20.0)),
        )

    @override
    def __eq__(self, other: object, /) -> bool:
        if not isinstance(other, Text):
            return False

        parent_result = super().__eq__(other)  # Check for ID
        if parent_result is not NotImplemented:
            return parent_result

        return (
            self.element_type == other.element_type
            and self.text == other.text
            and self.color == other.color
            and self.size_px == other.size_px
            and self.position == other.position
        )
