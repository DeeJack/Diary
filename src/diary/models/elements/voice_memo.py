"""Represents a VoiceMemo element that can be placed on a page"""

from dataclasses import dataclass
from typing import Any, cast, override

from diary.config import settings
from diary.models.page_element import PageElement
from diary.models.point import Point


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
        asset_id: str | None = None,
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
        self.asset_id: str | None = asset_id

    @override
    def to_dict(self) -> dict[str, Any]:
        """Serialize this voice memo to a dictionary for JSON storage"""
        result: dict[str, Any] = {
            settings.SERIALIZATION_KEYS.ELEMENT_TYPE.value: self.element_type,
            settings.SERIALIZATION_KEYS.ELEMENT_ID.value: self.element_id,
            settings.SERIALIZATION_KEYS.POSITION.value: [
                self.position.x,
                self.position.y,
                self.position.pressure,
            ],
            settings.SERIALIZATION_KEYS.DURATION.value: self.duration,
            settings.SERIALIZATION_KEYS.PATH.value: self.audio_path,
            settings.SERIALIZATION_KEYS.TRANSCRIPT.value: self.transcript,
            settings.SERIALIZATION_KEYS.CREATED_AT.value: self.created_at,
            settings.SERIALIZATION_KEYS.WIDTH.value: self.width,
            settings.SERIALIZATION_KEYS.HEIGHT.value: self.height,
        }

        # Use asset_id if available, otherwise fall back to inline data
        if self.asset_id:
            result[settings.SERIALIZATION_KEYS.ASSET_ID.value] = self.asset_id
        elif self.audio_data:
            result[settings.SERIALIZATION_KEYS.DATA.value] = self.audio_data.hex()

        return result

    @classmethod
    @override
    def from_dict(cls, data: dict[str, Any]) -> "VoiceMemo":
        """Deserialize this voice memo from a dictionary loaded from JSON"""
        # Support both new format (serialization keys) and legacy short keys
        pos_key = settings.SERIALIZATION_KEYS.POSITION.value
        position_data: list[float] = data.get(pos_key) or data.get("p", [0, 0, 1])
        position = Point(
            x=position_data[0], y=position_data[1], pressure=position_data[2]
        )

        # Check for asset_id first (new format)
        asset_id = data.get(settings.SERIALIZATION_KEYS.ASSET_ID.value)
        audio_data = None

        # Fall back to inline data if no asset_id
        if not asset_id:
            data_key = settings.SERIALIZATION_KEYS.DATA.value
            raw_data = data.get(data_key) or data.get("d")
            if raw_data:
                try:
                    audio_data = bytes.fromhex(raw_data)
                except ValueError:
                    audio_data = None

        # Get other fields with fallback to legacy keys
        duration_key = settings.SERIALIZATION_KEYS.DURATION.value
        path_key = settings.SERIALIZATION_KEYS.PATH.value
        transcript_key = settings.SERIALIZATION_KEYS.TRANSCRIPT.value
        created_key = settings.SERIALIZATION_KEYS.CREATED_AT.value
        width_key = settings.SERIALIZATION_KEYS.WIDTH.value
        height_key = settings.SERIALIZATION_KEYS.HEIGHT.value
        id_key = settings.SERIALIZATION_KEYS.ELEMENT_ID.value

        return cls(
            position=position,
            duration=cast(float, data.get(duration_key) or data.get("du", 0.0)),
            audio_path=data.get(path_key) or data.get("ap"),
            audio_data=audio_data,
            transcript=data.get(transcript_key) or data.get("t"),
            created_at=data.get(created_key) or data.get("c"),
            width=cast(float, data.get(width_key) or data.get("w", 50.0)),
            height=cast(float, data.get(height_key) or data.get("h", 50.0)),
            element_id=data.get(id_key) or data.get("id"),
            asset_id=asset_id,
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
            and self.asset_id == other.asset_id
        )
