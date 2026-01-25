"""Asset model for binary data (images, videos, audio)"""

import hashlib
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AssetType(Enum):
    """Type of binary asset"""

    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"


@dataclass
class Asset:
    """Represents a binary asset stored separately from page data"""

    asset_id: str
    asset_type: AssetType
    mime_type: str
    data: bytes | None = None
    checksum: str | None = None

    def __post_init__(self) -> None:
        """Calculate checksum if data is present and checksum is not set"""
        if self.data is not None and self.checksum is None:
            self.checksum = self._calculate_checksum(self.data)

    @staticmethod
    def _calculate_checksum(data: bytes) -> str:
        """Calculate SHA-256 checksum of data"""
        return hashlib.sha256(data).hexdigest()

    @classmethod
    def create(
        cls,
        asset_type: AssetType,
        mime_type: str,
        data: bytes,
    ) -> "Asset":
        """Create a new Asset with generated UUID"""
        return cls(
            asset_id=uuid.uuid4().hex,
            asset_type=asset_type,
            mime_type=mime_type,
            data=data,
        )

    @classmethod
    def from_image_bytes(cls, data: bytes, mime_type: str = "image/png") -> "Asset":
        """Create an image asset from raw bytes"""
        return cls.create(AssetType.IMAGE, mime_type, data)

    @classmethod
    def from_audio_bytes(cls, data: bytes, mime_type: str = "audio/wav") -> "Asset":
        """Create an audio asset from raw bytes"""
        return cls.create(AssetType.AUDIO, mime_type, data)

    @classmethod
    def from_video_bytes(cls, data: bytes, mime_type: str = "video/mp4") -> "Asset":
        """Create a video asset from raw bytes"""
        return cls.create(AssetType.VIDEO, mime_type, data)

    def to_manifest_entry(self) -> dict[str, Any]:
        """Return manifest entry (metadata only, no binary data)"""
        return {
            "aid": self.asset_id,
            "atype": self.asset_type.value,
            "mime": self.mime_type,
            "csum": self.checksum,
            "size": len(self.data) if self.data else 0,
        }

    @classmethod
    def from_manifest_entry(
        cls, entry: dict[str, Any], data: bytes | None = None
    ) -> "Asset":
        """Reconstruct Asset from manifest entry and optional binary data"""
        return cls(
            asset_id=entry["aid"],
            asset_type=AssetType(entry["atype"]),
            mime_type=entry["mime"],
            data=data,
            checksum=entry.get("csum"),
        )

    def verify_checksum(self) -> bool:
        """Verify that the data matches the stored checksum"""
        if self.data is None or self.checksum is None:
            return False
        return self._calculate_checksum(self.data) == self.checksum


@dataclass
class AssetIndex:
    """Index of all assets in an archive"""

    assets: dict[str, Asset] = field(default_factory=dict)

    def add(self, asset: Asset) -> None:
        """Add an asset to the index"""
        self.assets[asset.asset_id] = asset

    def get(self, asset_id: str) -> Asset | None:
        """Get an asset by ID"""
        return self.assets.get(asset_id)

    def remove(self, asset_id: str) -> Asset | None:
        """Remove an asset from the index"""
        return self.assets.pop(asset_id, None)

    def __contains__(self, asset_id: str) -> bool:
        return asset_id in self.assets

    def __iter__(self):
        return iter(self.assets.values())

    def __len__(self) -> int:
        return len(self.assets)

    def to_manifest_entries(self) -> list[dict[str, Any]]:
        """Return list of manifest entries for all assets"""
        return [asset.to_manifest_entry() for asset in self.assets.values()]

    @classmethod
    def from_manifest_entries(
        cls, entries: list[dict[str, Any]], asset_data: dict[str, bytes] | None = None
    ) -> "AssetIndex":
        """Reconstruct AssetIndex from manifest entries"""
        index = cls()
        for entry in entries:
            data = asset_data.get(entry["aid"]) if asset_data else None
            index.add(Asset.from_manifest_entry(entry, data))
        return index
