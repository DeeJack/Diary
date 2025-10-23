"""Represents a VoiceMemo element that can be placed on a page"""

from dataclasses import dataclass
from typing import cast, override, Any

from diary.config import settings
from diary.models.point import Point
from diary.models.page_element import PageElement


@dataclass
class VoiceMemo(PageElement):
    """Represents a Voice Memo element on a page"""

    def __init__(
        self,
        position: Point,
        duration: float,
        audio_path: str | None = None,
        audio_data: bytes | None = None,
        transcript: str | None = None,
        created_at: float | None = None,
        width: float = 50.0,
        height: float = 50.0,
        element_id: str | None = None,
    ):
        super().__init__("voice_memo", element_id)
        self.position: Point = position
        self.duration: float = duration  # Duration in seconds
        self.audio_path: str | None = audio_path
        self.audio_data: bytes | None = audio_data
        self.transcript: str | None = transcript
        self.created_at: float | None = created_at
        self.width: float = width  # Visual representation size
        self.height: float = height

    @override
    def intersects(self, pos: Point, radius: float) -> bool:
        """Check if this voice memo intersects with a circle at the given position and radius"""
        # Simple bounding box check for the visual representation
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
        """Serialize this voice memo to a dictionary for JSON storage"""
        return {
            settings.SERIALIZATION_KEYS.ELEMENT_TYPE.value: self.element_type,
            settings.SERIALIZATION_KEYS.ELEMENT_ID.value: self.element_id,
            settings.SERIALIZATION_KEYS.POSITION.value: [
                self.position.x,
                self.position.y,
                self.position.pressure,
            ],
            settings.SERIALIZATION_KEYS.DURATION.value: self.duration,
            settings.SERIALIZATION_KEYS.PATH.value: self.audio_path,
            settings.SERIALIZATION_KEYS.DATA.value: self.audio_data.hex()
            if self.audio_data
            else None,
            settings.SERIALIZATION_KEYS.TRANSCRIPT.value: self.transcript,
            settings.SERIALIZATION_KEYS.CREATED_AT.value: self.created_at,
            settings.SERIALIZATION_KEYS.WIDTH.value: self.width,
            settings.SERIALIZATION_KEYS.HEIGHT.value: self.height,
        }

    @classmethod
    @override
    def from_dict(cls, data: dict[str, Any]) -> "VoiceMemo":
        """Deserialize this voice memo from a dictionary loaded from JSON"""
        position_data: list[float] = data.get("p", {})
        position = Point(
            x=position_data[0], y=position_data[1], pressure=position_data[2]
        )

        audio_data = None
        if data.get("d"):
            try:
                audio_data = bytes.fromhex(data["d"])
            except ValueError:
                audio_data = None

        return cls(
            position=position,
            duration=cast(float, data.get("du", 0.0)),
            audio_path=data.get("p"),
            audio_data=audio_data,
            transcript=data.get("t"),
            created_at=data.get("c"),
            width=cast(float, data.get("w", 50.0)),
            height=cast(float, data.get("h", 50.0)),
            element_id=data.get("id"),
        )

    @override
    def __eq__(self, other: object, /) -> bool:
        if not other or not isinstance(other, VoiceMemo):
            return False

        # Use fast UUID check from parent class
        parent_result = super().__eq__(other)
        if parent_result != NotImplemented:
            return parent_result

        # Fallback to detailed comparison
        return (
            self.element_type == other.element_type
            and self.position == other.position
            and self.duration == other.duration
            and self.audio_path == other.audio_path
            and self.audio_data == other.audio_data
            and self.transcript == other.transcript
            and self.created_at == other.created_at
            and self.width == other.width
            and self.height == other.height
        )
