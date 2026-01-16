"""Archive manifest model for the encrypted archive format"""

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ArchiveManifest:
    """Manifest containing metadata about the archive contents"""

    version: int = 2
    created_at: float = field(default_factory=time.time)
    modified_at: float = field(default_factory=time.time)
    notebook_id: str = ""
    notebook_metadata: dict[str, Any] = field(default_factory=dict)
    page_ids: list[str] = field(default_factory=list)
    assets: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize manifest to dictionary"""
        return {
            "ver": self.version,
            "created": self.created_at,
            "modified": self.modified_at,
            "nbid": self.notebook_id,
            "nbmeta": self.notebook_metadata,
            "pages": self.page_ids,
            "assets": self.assets,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ArchiveManifest":
        """Deserialize manifest from dictionary"""
        return cls(
            version=data.get("ver", 2),
            created_at=data.get("created", time.time()),
            modified_at=data.get("modified", time.time()),
            notebook_id=data.get("nbid", ""),
            notebook_metadata=data.get("nbmeta", {}),
            page_ids=data.get("pages", []),
            assets=data.get("assets", []),
        )

    def update_modified(self) -> None:
        """Update the modified timestamp"""
        self.modified_at = time.time()
