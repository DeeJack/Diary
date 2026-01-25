"""Represents a Video element that can be placed on a page"""

from base64 import b64decode, b64encode
from dataclasses import dataclass
from typing import Any, cast, override

from diary.config import settings
from diary.models.page_element import PageElement
from diary.models.point import Point


@dataclass
class Video(PageElement):
    """Represents a Video element on a page"""

    def __init__(
        self,
        position: Point,
        width: float,
        height: float,
        asset_id: str | None = None,
        video_data: bytes | None = None,
        rotation: float = 0.0,
        duration: float = 0.0,
        thumbnail_data: bytes | None = None,
        thumbnail_asset_id: str | None = None,
        element_id: str | None = None,
    ):
        super().__init__("video", element_id)
        self.position: Point = position
        self.width: float = width
        self.height: float = height
        self.asset_id: str | None = asset_id
        self.video_data: bytes | None = video_data
        self.rotation: float = rotation
        self.duration: float = duration  # Duration in seconds
        self.thumbnail_data: bytes | None = thumbnail_data
        self.thumbnail_asset_id: str | None = thumbnail_asset_id

    @override
    def to_dict(self) -> dict[str, Any]:
        """Serialize this video to a dictionary for storage"""
        result: dict[str, Any] = {
            settings.SERIALIZATION_KEYS.ELEMENT_TYPE.value: self.element_type,
            settings.SERIALIZATION_KEYS.ELEMENT_ID.value: self.element_id,
            settings.SERIALIZATION_KEYS.POSITION.value: [
                self.position.x,
                self.position.y,
                self.position.pressure,
            ],
            settings.SERIALIZATION_KEYS.WIDTH.value: self.width,
            settings.SERIALIZATION_KEYS.HEIGHT.value: self.height,
            settings.SERIALIZATION_KEYS.ROTATION.value: self.rotation,
            settings.SERIALIZATION_KEYS.DURATION.value: self.duration,
        }

        if self.asset_id:
            result[settings.SERIALIZATION_KEYS.ASSET_ID.value] = self.asset_id
        elif self.video_data:
            result[settings.SERIALIZATION_KEYS.DATA.value] = b64encode(self.video_data)

        if self.thumbnail_asset_id:
            result["thumb"] = self.thumbnail_asset_id
        elif self.thumbnail_data:
            result["thumb_data"] = b64encode(self.thumbnail_data)

        return result

    @classmethod
    @override
    def from_dict(cls, data: dict[str, Any]) -> "Video":
        """Deserialize this video from a dictionary"""
        position_data: list[float] = data.get(
            settings.SERIALIZATION_KEYS.POSITION.value, [0, 0, 1]
        )
        position = Point(
            x=position_data[0],
            y=position_data[1],
            pressure=position_data[2] if len(position_data) > 2 else 1.0,
        )

        asset_id = data.get(settings.SERIALIZATION_KEYS.ASSET_ID.value)
        video_data = None
        if not asset_id and data.get(settings.SERIALIZATION_KEYS.DATA.value):
            try:
                video_data = b64decode(data[settings.SERIALIZATION_KEYS.DATA.value])
            except (ValueError, TypeError):
                video_data = None

        thumbnail_data = None
        if not data.get("thumb") and data.get("thumb_data"):
            try:
                thumbnail_data = b64decode(data["thumb_data"])
            except (ValueError, TypeError):
                thumbnail_data = None

        video = cls(
            position=position,
            width=cast(float, data.get(settings.SERIALIZATION_KEYS.WIDTH.value, 320.0)),
            height=cast(
                float, data.get(settings.SERIALIZATION_KEYS.HEIGHT.value, 240.0)
            ),
            asset_id=asset_id,
            rotation=cast(
                float, data.get(settings.SERIALIZATION_KEYS.ROTATION.value, 0.0)
            ),
            duration=cast(
                float, data.get(settings.SERIALIZATION_KEYS.DURATION.value, 0.0)
            ),
            thumbnail_data=thumbnail_data,
            thumbnail_asset_id=data.get("thumb"),
            element_id=data.get(settings.SERIALIZATION_KEYS.ELEMENT_ID.value),
        )
        video.video_data = video_data
        return video

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
            and self.asset_id == other.asset_id
            and self.video_data == other.video_data
            and self.rotation == other.rotation
            and self.duration == other.duration
            and self.thumbnail_data == other.thumbnail_data
            and self.thumbnail_asset_id == other.thumbnail_asset_id
        )
