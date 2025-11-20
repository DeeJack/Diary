"""Represents an Video element that can be placed on a page"""

from base64 import b64encode
from dataclasses import dataclass
from typing import Any, cast, override

from diary.config import settings
from diary.models.page_element import PageElement
from diary.models.point import Point


@dataclass
class Video(PageElement):
    """Represents an Video element on a page"""

    def __init__(
        self,
        position: Point,
        width: float,
        height: float,
        video_path: str | None = None,
        video_data: bytes | None = None,
        rotation: float = 0.0,
        element_id: str | None = None,
    ):
        super().__init__("video", element_id)
        self.position: Point = position
        self.width: float = width
        self.height: float = height
        self.video_path: str | None = video_path
        self.video_data: bytes | None = video_data
        self.rotation: float = rotation

    @override
    def to_dict(self) -> dict[str, Any]:
        """Serialize this video to a dictionary for JSON storage"""
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
            settings.SERIALIZATION_KEYS.PATH.value: self.video_path,
            settings.SERIALIZATION_KEYS.DATA.value: b64encode(self.video_data)
            if self.video_data
            else None,
            settings.SERIALIZATION_KEYS.ROTATION.value: self.rotation,
        }

    @classmethod
    @override
    def from_dict(cls, data: dict[str, Any]) -> "Video":
        """Deserialize this video from a dictionary loaded from JSON"""
        position_data: list[float] = data.get(
            settings.SERIALIZATION_KEYS.POSITION.value, []
        )
        position = Point(
            x=position_data[0],
            y=position_data[1],
            pressure=position_data[2],
        )

        video_data = data.get(settings.SERIALIZATION_KEYS.DATA.value, None)

        return cls(
            position=position,
            width=cast(float, data.get(settings.SERIALIZATION_KEYS.WIDTH.value, 100.0)),
            height=cast(
                float, data.get(settings.SERIALIZATION_KEYS.HEIGHT.value, 100.0)
            ),
            video_path=data.get(settings.SERIALIZATION_KEYS.PATH.value),
            video_data=video_data,
            rotation=cast(
                float, data.get(settings.SERIALIZATION_KEYS.ROTATION.value, 0.0)
            ),
            element_id=data.get(settings.SERIALIZATION_KEYS.ELEMENT_ID.value),
        )

    @override
    def __eq__(self, other: object, /) -> bool:
        if not other or not isinstance(other, Video):
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
            and self.video_path == other.video_path
            and self.video_data == other.video_data
            and self.rotation == other.rotation
        )
