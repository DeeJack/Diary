"""Asset cache for incremental saves"""

from diary.models.asset import Asset, AssetIndex


class AssetCache:
    """
    Cache for asset bytes to enable incremental saves.

    When saving, unchanged assets can be reused from the cache
    instead of being re-encoded from memory.
    """

    def __init__(self) -> None:
        self._asset_bytes: dict[str, bytes] = {}
        self._checksums: dict[str, str] = {}

    def populate_from_assets(self, assets: AssetIndex) -> None:
        """Populate cache from loaded assets"""
        for asset in assets:
            if asset.data is not None:
                self._asset_bytes[asset.asset_id] = asset.data
                if asset.checksum:
                    self._checksums[asset.asset_id] = asset.checksum

    def get_asset_bytes(self, asset_id: str) -> bytes | None:
        """Get cached asset bytes"""
        return self._asset_bytes.get(asset_id)

    def get_checksum(self, asset_id: str) -> str | None:
        """Get cached checksum for an asset"""
        return self._checksums.get(asset_id)

    def set_asset_bytes(self, asset_id: str, data: bytes, checksum: str | None = None) -> None:
        """Cache asset bytes"""
        self._asset_bytes[asset_id] = data
        if checksum:
            self._checksums[asset_id] = checksum

    def add_asset(self, asset: Asset) -> None:
        """Add an asset to the cache"""
        if asset.data is not None:
            self._asset_bytes[asset.asset_id] = asset.data
            if asset.checksum:
                self._checksums[asset.asset_id] = asset.checksum

    def remove_asset(self, asset_id: str) -> None:
        """Remove asset from cache"""
        self._asset_bytes.pop(asset_id, None)
        self._checksums.pop(asset_id, None)

    def clear(self) -> None:
        """Clear all cached data"""
        self._asset_bytes.clear()
        self._checksums.clear()

    def get_all_bytes(self) -> dict[str, bytes]:
        """Get all cached asset bytes for incremental save"""
        return dict(self._asset_bytes)

    def __contains__(self, asset_id: str) -> bool:
        return asset_id in self._asset_bytes

    def __len__(self) -> int:
        return len(self._asset_bytes)
