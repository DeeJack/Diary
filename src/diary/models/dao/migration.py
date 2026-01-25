"""Migration utilities for converting between file formats"""

import logging
from pathlib import Path
from typing import Callable

from diary.models.asset import Asset, AssetIndex, AssetType
from diary.models.dao.archive_dao import ArchiveDAO
from diary.models.dao.legacy_loader import load_legacy_notebook, load_legacy_notebooks
from diary.models.elements.image import Image
from diary.models.elements.video import Video
from diary.models.elements.voice_memo import VoiceMemo
from diary.models.notebook import Notebook
from diary.utils import encryption


def detect_image_mime_type(data: bytes) -> str:
    """Detect MIME type from image header bytes"""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:2] == b"\xff\xd8":
        return "image/jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:4] == b"\x00\x00\x01\x00":
        return "image/x-icon"
    return "application/octet-stream"


def detect_audio_mime_type(data: bytes) -> str:
    """Detect MIME type from audio header bytes"""
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return "audio/wav"
    if data[:3] == b"ID3" or data[:2] == b"\xff\xfb":
        return "audio/mpeg"
    if data[:4] == b"fLaC":
        return "audio/flac"
    if data[:4] == b"OggS":
        return "audio/ogg"
    return "audio/octet-stream"


def detect_video_mime_type(data: bytes) -> str:
    """Detect MIME type from video header bytes"""
    # Check for common video formats
    if len(data) >= 12:
        # MP4/MOV (ftyp box)
        if data[4:8] == b"ftyp":
            ftyp_brand = data[8:12]
            if ftyp_brand in (b"isom", b"iso2", b"mp41", b"mp42", b"avc1"):
                return "video/mp4"
            if ftyp_brand in (b"qt  ", b"MSNV"):
                return "video/quicktime"
            return "video/mp4"  # Default for ftyp
        # WebM/MKV (EBML header)
        if data[:4] == b"\x1a\x45\xdf\xa3":
            # Check for WebM doctype
            if b"webm" in data[:64]:
                return "video/webm"
            return "video/x-matroska"
    # AVI
    if data[:4] == b"RIFF" and data[8:12] == b"AVI ":
        return "video/x-msvideo"
    # MPEG
    if data[:4] == b"\x00\x00\x01\xba" or data[:4] == b"\x00\x00\x01\xb3":
        return "video/mpeg"
    return "video/octet-stream"


class ArchiveMigration:
    """Handles migration from legacy format to archive format"""

    @staticmethod
    def migrate_notebook(
        legacy_filepath: Path,
        new_filepath: Path,
        key_buffer: encryption.SecureBuffer,
        salt: bytes,
        progress: Callable[[int, int], None] | None = None,
    ) -> tuple[Notebook, AssetIndex]:
        """
        Migrate a notebook from legacy format to archive format.

        1. Load legacy notebook
        2. Extract inline binary data to Asset objects
        3. Update element references to use asset_id
        4. Save in new archive format

        Args:
            legacy_filepath: Path to legacy encrypted file
            new_filepath: Path for new archive file
            key_buffer: Derived encryption key
            salt: Salt for encryption
            progress: Optional progress callback

        Returns:
            Tuple of (migrated Notebook, AssetIndex)
        """
        logger = logging.getLogger("Migration")
        logger.info("Starting migration from %s to %s", legacy_filepath, new_filepath)

        # Load legacy notebook
        notebook = load_legacy_notebook(legacy_filepath, key_buffer, progress)
        logger.debug("Loaded notebook with %d pages", len(notebook.pages))

        # Extract assets from all pages
        assets = AssetIndex()
        total_assets = 0

        for page in notebook.pages:
            for element in page.elements:
                if isinstance(element, Image) and element.image_data:
                    # Extract image data to asset
                    mime_type = detect_image_mime_type(element.image_data)
                    asset = Asset.create(
                        AssetType.IMAGE,
                        mime_type,
                        element.image_data,
                    )
                    assets.add(asset)

                    # Update element to reference asset
                    element.asset_id = asset.asset_id
                    element.image_data = None  # Clear inline data

                    total_assets += 1
                    logger.debug(
                        "Extracted image asset: %s (%s)",
                        asset.asset_id,
                        mime_type,
                    )

                elif isinstance(element, VoiceMemo) and element.audio_data:
                    # Extract audio data to asset
                    mime_type = detect_audio_mime_type(element.audio_data)
                    asset = Asset.create(
                        AssetType.AUDIO,
                        mime_type,
                        element.audio_data,
                    )
                    assets.add(asset)

                    # Update element to reference asset
                    element.asset_id = asset.asset_id
                    element.audio_data = None  # Clear inline data

                    total_assets += 1
                    logger.debug(
                        "Extracted audio asset: %s (%s)",
                        asset.asset_id,
                        mime_type,
                    )
                elif isinstance(element, Video) and element.video_data:
                    # Extract video data to asset
                    mime_type = detect_video_mime_type(element.video_data)
                    asset = Asset.create(
                        AssetType.VIDEO,
                        mime_type,
                        element.video_data,
                    )
                    assets.add(asset)

                    # Update element to reference asset
                    element.asset_id = asset.asset_id
                    element.video_data = None  # Clear inline data

                    total_assets += 1
                    logger.debug(
                        "Extracted video asset: %s (%s)",
                        asset.asset_id,
                        mime_type,
                    )

                if isinstance(element, Video) and element.thumbnail_data:
                    # Extract thumbnail to asset
                    mime_type = detect_image_mime_type(element.thumbnail_data)
                    asset = Asset.create(
                        AssetType.IMAGE,
                        mime_type,
                        element.thumbnail_data,
                    )
                    assets.add(asset)

                    element.thumbnail_asset_id = asset.asset_id
                    element.thumbnail_data = None

                    total_assets += 1
                    logger.debug(
                        "Extracted video thumbnail asset: %s (%s)",
                        asset.asset_id,
                        mime_type,
                    )
                elif isinstance(element, Video) and element.video_data:
                    # Extract video data to asset
                    mime_type = detect_video_mime_type(element.video_data)
                    asset = Asset.create(
                        AssetType.VIDEO,
                        mime_type,
                        element.video_data,
                    )
                    assets.add(asset)

                    # Update element to reference asset
                    element.asset_id = asset.asset_id
                    element.video_data = None  # Clear inline data

                    total_assets += 1
                    logger.debug(
                        "Extracted video asset: %s (%s)",
                        asset.asset_id,
                        mime_type,
                    )

        logger.info("Extracted %d assets from notebook", total_assets)

        # Save in new archive format (single notebook archive)
        ArchiveDAO.save_all(
            [notebook],
            {notebook.notebook_id: assets},
            new_filepath,
            key_buffer,
            salt,
            None,
            progress,
        )
        logger.info("Migration completed successfully")

        return notebook, assets

    @staticmethod
    def migrate_notebooks(
        legacy_filepath: Path,
        new_filepath: Path,
        key_buffer: encryption.SecureBuffer,
        salt: bytes,
        progress: Callable[[int, int], None] | None = None,
    ) -> tuple[list[Notebook], dict[str, AssetIndex]]:
        """
        Migrate multiple notebooks from legacy format to archive format.

        Args:
            legacy_filepath: Path to legacy encrypted file with multiple notebooks
            new_filepath: Path for new archive file
            key_buffer: Derived encryption key
            salt: Salt for encryption
            progress: Optional progress callback

        Returns:
            Tuple of (list of migrated Notebooks, asset index per notebook)
        """
        logger = logging.getLogger("Migration")
        logger.info("Starting multi-notebook migration")

        # Load legacy notebooks
        notebooks = load_legacy_notebooks(legacy_filepath, key_buffer, progress)
        logger.debug("Loaded %d notebooks", len(notebooks))

        if not notebooks:
            return [], {}

        assets_by_notebook: dict[str, AssetIndex] = {}
        total_assets = 0

        for notebook in notebooks:
            assets = ArchiveMigration.extract_assets_from_notebook(notebook)
            assets_by_notebook[notebook.notebook_id] = assets
            total_assets += len(assets)

        logger.info("Extracted %d assets from notebooks", total_assets)

        ArchiveDAO.save_all(
            notebooks,
            assets_by_notebook,
            new_filepath,
            key_buffer,
            salt,
            None,
            progress,
        )
        logger.info("Migration completed for all notebooks")

        return notebooks, assets_by_notebook

    @staticmethod
    def inject_asset_data(notebook: Notebook, assets: AssetIndex) -> None:
        """
        Inject asset data back into elements after loading from archive.

        This is useful when you need the inline data (e.g., for display)
        but loaded from the archive format where data is stored separately.

        Args:
            notebook: Notebook to update
            assets: Asset index with binary data
        """
        for page in notebook.pages:
            for element in page.elements:
                if isinstance(element, Image) and element.asset_id:
                    asset = assets.get(element.asset_id)
                    if asset and asset.data:
                        element.image_data = asset.data

                elif isinstance(element, VoiceMemo) and element.asset_id:
                    asset = assets.get(element.asset_id)
                    if asset and asset.data:
                        element.audio_data = asset.data
                elif isinstance(element, Video) and element.asset_id:
                    asset = assets.get(element.asset_id)
                    if asset and asset.data:
                        element.video_data = asset.data
                if isinstance(element, Video) and element.thumbnail_asset_id:
                    asset = assets.get(element.thumbnail_asset_id)
                    if asset and asset.data:
                        element.thumbnail_data = asset.data

    @staticmethod
    def extract_assets_from_notebook(notebook: Notebook) -> AssetIndex:
        """
        Extract binary data from elements into an AssetIndex.

        For elements with inline data (image_data, audio_data), creates
        assets and updates elements to reference them by asset_id.

        Args:
            notebook: Notebook to extract assets from

        Returns:
            AssetIndex containing all extracted assets
        """
        assets = AssetIndex()

        for page in notebook.pages:
            for element in page.elements:
                if isinstance(element, Image):
                    if element.image_data and not element.asset_id:
                        # Has inline data but no asset_id - create new asset
                        mime_type = detect_image_mime_type(element.image_data)
                        asset = Asset.create(
                            AssetType.IMAGE,
                            mime_type,
                            element.image_data,
                        )
                        assets.add(asset)
                        element.asset_id = asset.asset_id
                    elif element.asset_id and element.image_data:
                        # Has both - preserve existing asset with current data
                        mime_type = detect_image_mime_type(element.image_data)
                        asset = Asset(
                            asset_id=element.asset_id,
                            asset_type=AssetType.IMAGE,
                            mime_type=mime_type,
                            data=element.image_data,
                        )
                        assets.add(asset)

                elif isinstance(element, VoiceMemo):
                    if element.audio_data and not element.asset_id:
                        mime_type = detect_audio_mime_type(element.audio_data)
                        asset = Asset.create(
                            AssetType.AUDIO,
                            mime_type,
                            element.audio_data,
                        )
                        assets.add(asset)
                        element.asset_id = asset.asset_id
                    elif element.asset_id and element.audio_data:
                        mime_type = detect_audio_mime_type(element.audio_data)
                        asset = Asset(
                            asset_id=element.asset_id,
                            asset_type=AssetType.AUDIO,
                            mime_type=mime_type,
                            data=element.audio_data,
                        )
                        assets.add(asset)
                elif isinstance(element, Video):
                    if element.video_data and not element.asset_id:
                        mime_type = detect_video_mime_type(element.video_data)
                        asset = Asset.create(
                            AssetType.VIDEO,
                            mime_type,
                            element.video_data,
                        )
                        assets.add(asset)
                        element.asset_id = asset.asset_id
                    elif element.asset_id and element.video_data:
                        mime_type = detect_video_mime_type(element.video_data)
                        asset = Asset(
                            asset_id=element.asset_id,
                            asset_type=AssetType.VIDEO,
                            mime_type=mime_type,
                            data=element.video_data,
                        )
                        assets.add(asset)
                    if element.thumbnail_data and not element.thumbnail_asset_id:
                        mime_type = detect_image_mime_type(element.thumbnail_data)
                        asset = Asset.create(
                            AssetType.IMAGE,
                            mime_type,
                            element.thumbnail_data,
                        )
                        assets.add(asset)
                        element.thumbnail_asset_id = asset.asset_id
                    elif element.thumbnail_asset_id and element.thumbnail_data:
                        mime_type = detect_image_mime_type(element.thumbnail_data)
                        asset = Asset(
                            asset_id=element.thumbnail_asset_id,
                            asset_type=AssetType.IMAGE,
                            mime_type=mime_type,
                            data=element.thumbnail_data,
                        )
                        assets.add(asset)

        return assets
