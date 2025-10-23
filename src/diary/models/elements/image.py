"""Represents an Image element that can be placed on a page"""

from dataclasses import dataclass
from typing import cast, override, Any

from diary.config import settings
from diary.models.point import Point
from diary.models.page_element import PageElement


@dataclass
class Image(PageElement):
    """Represents an Image element on a page"""

    def __init__(
        self,
        position: Point,
        width: float,
        height: float,
        image_path: str | None = None,
        image_data: bytes | None = None,
        rotation: float = 0.0,
        element_id: str | None = None,
    ):
        super().__init__("image", element_id)
        self.position: Point = position
        self.width: float = width
        self.height: float = height
        self.image_path: str | None = image_path
        self.image_data: bytes | None = image_data
        self.rotation: float = rotation

    @override
    def intersects(self, pos: Point, radius: float) -> bool:
        """Check if this image intersects with a circle at the given position and radius"""
        # Simple bounding box check
        left = self.position.x
        right = self.position.x + self.width
        top = self.position.y
        bottom = self.position.y + self.height

        # Check if point is inside the bounding box expanded by radius
        return (
            left - radius <= pos.x <= right + radius
            and top - radius <= pos.y <= bottom + radius
        )

    @override
    def to_dict(self) -> dict[str, Any]:
        """Serialize this image to a dictionary for JSON storage"""
        return {
            settings.SERIALIZATION_KEYS.ELEMENT_TYPE.value: self.element_type,
            settings.SERIALIZATION_KEYS.ELEMENT_ID.value: self.element_id,
            settings.SERIALIZATION_KEYS.POSITION.value: [
                self.position.x,
                self.position.y,
                self.position.pressure,
            ],
            settings.SERIALIZATION_KEYS.WIDTH.value: self.width,
            settings.SERIALIZATION_KEYS.HEIGHT.value: self.height,
            settings.SERIALIZATION_KEYS.PATH.value: self.image_path,
            settings.SERIALIZATION_KEYS.DATA.value: self.image_data.hex()
            if self.image_data
            else None,
            settings.SERIALIZATION_KEYS.ROTATION.value: self.rotation,
        }

    @classmethod
    @override
    def from_dict(cls, data: dict[str, Any]) -> "Image":
        """Deserialize this image from a dictionary loaded from JSON"""
        position_data: list[float] = data.get(
            settings.SERIALIZATION_KEYS.POSITION.value, []
        )
        position = Point(
            x=position_data[0],
            y=position_data[1],
            pressure=position_data[2],
        )

        image_data = None
        if data.get(settings.SERIALIZATION_KEYS.DATA.value):
            try:
                image_data = bytes.fromhex(data[settings.SERIALIZATION_KEYS.DATA.value])
            except ValueError:
                image_data = None

        return cls(
            position=position,
            width=cast(float, data.get(settings.SERIALIZATION_KEYS.WIDTH.value, 100.0)),
            height=cast(
                float, data.get(settings.SERIALIZATION_KEYS.HEIGHT.value, 100.0)
            ),
            image_path=data.get(settings.SERIALIZATION_KEYS.PATH.value),
            image_data=image_data,
            rotation=cast(
                float, data.get(settings.SERIALIZATION_KEYS.ROTATION.value, 0.0)
            ),
            element_id=data.get(settings.SERIALIZATION_KEYS.ELEMENT_ID.value),
        )

    @override
    def __eq__(self, other: object, /) -> bool:
        if not other or not isinstance(other, Image):
            return False

        # Use fast UUID check from parent class
        parent_result = super().__eq__(other)
        if parent_result != NotImplemented:
            return parent_result

        # Fallback to detailed comparison
        return (
            self.element_type == other.element_type
            and self.position == other.position
            and self.width == other.width
            and self.height == other.height
            and self.image_path == other.image_path
            and self.image_data == other.image_data
            and self.rotation == other.rotation
        )
