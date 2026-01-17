"""Tests for the archive-based save system"""

import tempfile
from pathlib import Path

import msgpack
import zstd

from diary.models.asset import Asset, AssetIndex, AssetType
from diary.models.dao.archive_dao import ArchiveDAO
from diary.models.dao.asset_cache import AssetCache
from diary.models.dao.migration import (
    ArchiveMigration,
    detect_audio_mime_type,
    detect_image_mime_type,
    detect_video_mime_type,
)
from diary.models.elements.image import Image
from diary.models.elements.stroke import Stroke
from diary.models.elements.video import Video
from diary.models.notebook import Notebook
from diary.models.page import Page
from diary.models.point import Point
from diary.utils.encryption import SecureBuffer, SecureEncryption


def _write_legacy_notebook(
    notebook: Notebook,
    filepath: Path,
    key: SecureBuffer,
    salt: bytes,
) -> None:
    notebook_encoded = msgpack.packb(notebook.to_dict(), use_bin_type=True)
    compressed_notebook = zstd.ZSTD_compress(notebook_encoded, 3)
    SecureEncryption.encrypt_bytes_to_file(
        compressed_notebook, filepath, key, salt, None
    )


def _save_single(
    notebook: Notebook,
    assets: AssetIndex,
    filepath: Path,
    key: SecureBuffer,
    salt: bytes,
    previous_asset_bytes: dict[str, bytes] | None = None,
) -> None:
    assets_by_notebook = {notebook.notebook_id: assets}
    previous_by_notebook = (
        {notebook.notebook_id: previous_asset_bytes}
        if previous_asset_bytes is not None
        else None
    )
    ArchiveDAO.save_all(
        [notebook],
        assets_by_notebook,
        filepath,
        key,
        salt,
        previous_by_notebook,
    )


def _load_single(
    filepath: Path,
    key: SecureBuffer,
) -> tuple[Notebook, AssetIndex]:
    notebooks, assets_by_notebook = ArchiveDAO.load_all(filepath, key)
    if not notebooks:
        return Notebook(pages=[Page()]), AssetIndex()
    notebook = notebooks[0]
    assets = assets_by_notebook.get(notebook.notebook_id, AssetIndex())
    return notebook, assets


class TestAsset:
    """Tests for the Asset model"""

    def test_create_image_asset(self):
        """Test creating an image asset"""
        data = b"\x89PNG\r\n\x1a\n" + b"test data"
        asset = Asset.from_image_bytes(data)

        assert asset.asset_type == AssetType.IMAGE
        assert asset.mime_type == "image/png"
        assert asset.data == data
        assert asset.checksum is not None

    def test_create_audio_asset(self):
        """Test creating an audio asset"""
        data = b"RIFF\x00\x00\x00\x00WAVEtest"
        asset = Asset.from_audio_bytes(data)

        assert asset.asset_type == AssetType.AUDIO
        assert asset.mime_type == "audio/wav"
        assert asset.data == data

    def test_create_video_asset(self):
        """Test creating a video asset"""
        data = b"\x00\x00\x00\x1cftypisom\x00\x00\x00\x00"
        asset = Asset.from_video_bytes(data)

        assert asset.asset_type == AssetType.VIDEO
        assert asset.mime_type == "video/mp4"
        assert asset.data == data

    def test_asset_checksum_verification(self):
        """Test that checksum verification works"""
        data = b"test data for checksum"
        asset = Asset.create(AssetType.IMAGE, "image/png", data)

        assert asset.verify_checksum()

        # Modify data and verify fails
        asset.data = b"modified data"
        assert not asset.verify_checksum()

    def test_asset_manifest_roundtrip(self):
        """Test serializing and deserializing asset manifest entry"""
        data = b"test data"
        asset = Asset.create(AssetType.IMAGE, "image/png", data)

        entry = asset.to_manifest_entry()
        restored = Asset.from_manifest_entry(entry, data)

        assert restored.asset_id == asset.asset_id
        assert restored.asset_type == asset.asset_type
        assert restored.mime_type == asset.mime_type
        assert restored.data == data


class TestAssetIndex:
    """Tests for the AssetIndex"""

    def test_add_and_get_asset(self):
        """Test adding and retrieving assets"""
        index = AssetIndex()
        asset = Asset.create(AssetType.IMAGE, "image/png", b"data")

        index.add(asset)
        assert asset.asset_id in index
        assert index.get(asset.asset_id) == asset

    def test_remove_asset(self):
        """Test removing assets"""
        index = AssetIndex()
        asset = Asset.create(AssetType.IMAGE, "image/png", b"data")

        index.add(asset)
        removed = index.remove(asset.asset_id)

        assert removed == asset
        assert asset.asset_id not in index

    def test_manifest_roundtrip(self):
        """Test serializing and deserializing asset index"""
        index = AssetIndex()
        asset1 = Asset.create(AssetType.IMAGE, "image/png", b"data1")
        asset2 = Asset.create(AssetType.AUDIO, "audio/wav", b"data2")

        index.add(asset1)
        index.add(asset2)

        entries = index.to_manifest_entries()
        asset_data = {
            asset1.asset_id: asset1.data,
            asset2.asset_id: asset2.data,
        }
        restored = AssetIndex.from_manifest_entries(entries, asset_data)

        assert len(restored) == 2
        assert asset1.asset_id in restored
        assert asset2.asset_id in restored


class TestArchiveDAO:
    """Tests for the ArchiveDAO"""

    def test_save_and_load_empty_notebook(self):
        """Test saving and loading an empty notebook"""
        notebook = Notebook()
        notebook.pages.append(Page())
        assets = AssetIndex()

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test.denc"
            salt = SecureEncryption.generate_salt()
            key = SecureEncryption.derive_key("testpass", salt)

            _save_single(notebook, assets, filepath, key, salt)
            loaded_notebook, loaded_assets = _load_single(filepath, key)

            assert loaded_notebook.notebook_id == notebook.notebook_id
            assert len(loaded_notebook.pages) == 1
            assert len(loaded_assets) == 0

    def test_save_and_load_with_strokes(self):
        """Test saving and loading notebook with strokes"""
        notebook = Notebook()
        page = Page()
        stroke = Stroke(
            points=[Point(0, 0, 1), Point(10, 10, 1), Point(20, 20, 1)],
            color="black",
            size=2.0,
            tool="pen",
        )
        page.add_element(stroke)
        notebook.pages.append(page)
        assets = AssetIndex()

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test.denc"
            salt = SecureEncryption.generate_salt()
            key = SecureEncryption.derive_key("testpass", salt)

            _save_single(notebook, assets, filepath, key, salt)
            loaded_notebook, _ = _load_single(filepath, key)

            loaded_page = loaded_notebook.pages[0]
            assert len(loaded_page.elements) == 1
            loaded_stroke = loaded_page.elements[0]
            assert isinstance(loaded_stroke, Stroke)
            assert len(loaded_stroke.points) == 3

    def test_save_and_load_with_image_asset(self):
        """Test saving and loading notebook with image asset"""
        notebook = Notebook()
        page = Page()

        # Create image with asset reference
        image = Image(
            position=Point(100, 100, 1),
            width=200,
            height=150,
            asset_id="test_img_asset",
        )
        page.add_element(image)
        notebook.pages.append(page)

        # Create asset
        assets = AssetIndex()
        asset = Asset(
            asset_id="test_img_asset",
            asset_type=AssetType.IMAGE,
            mime_type="image/png",
            data=b"\x89PNG\r\n\x1a\n" + b"test image data" * 10,
        )
        assets.add(asset)

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test.denc"
            salt = SecureEncryption.generate_salt()
            key = SecureEncryption.derive_key("testpass", salt)

            _save_single(notebook, assets, filepath, key, salt)
            loaded_notebook, loaded_assets = _load_single(filepath, key)

            # Verify image element
            loaded_page = loaded_notebook.pages[0]
            loaded_image = loaded_page.elements[0]
            assert isinstance(loaded_image, Image)
            assert loaded_image.asset_id == "test_img_asset"

            # Verify asset
            loaded_asset = loaded_assets.get("test_img_asset")
            assert loaded_asset is not None
            assert loaded_asset.data == asset.data

    def test_save_and_load_with_video(self):
        """Test saving and loading notebook with video element"""
        notebook = Notebook()
        page = Page()

        video = Video(
            position=Point(50, 50, 1),
            width=320,
            height=240,
            asset_id="test_video_asset",
            duration=10.5,
        )
        page.add_element(video)
        notebook.pages.append(page)

        assets = AssetIndex()
        asset = Asset(
            asset_id="test_video_asset",
            asset_type=AssetType.VIDEO,
            mime_type="video/mp4",
            data=b"\x00\x00\x00\x1cftypisom" + b"video data" * 10,
        )
        assets.add(asset)

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test.denc"
            salt = SecureEncryption.generate_salt()
            key = SecureEncryption.derive_key("testpass", salt)

            _save_single(notebook, assets, filepath, key, salt)
            loaded_notebook, loaded_assets = _load_single(filepath, key)

            loaded_video = loaded_notebook.pages[0].elements[0]
            assert isinstance(loaded_video, Video)
            assert loaded_video.asset_id == "test_video_asset"
            assert loaded_video.duration == 10.5

    def test_format_detection(self):
        """Test that format detection works correctly"""
        notebook = Notebook()
        notebook.pages.append(Page())
        assets = AssetIndex()

        with tempfile.TemporaryDirectory() as tmpdir:
            archive_path = Path(tmpdir) / "archive.denc"
            legacy_path = Path(tmpdir) / "legacy.enc"
            salt = SecureEncryption.generate_salt()
            key = SecureEncryption.derive_key("testpass", salt)

            # Save archive format
            _save_single(notebook, assets, archive_path, key, salt)
            assert ArchiveDAO.detect_format(archive_path) == "archive_v2"

            # Save legacy format
            _write_legacy_notebook(notebook, legacy_path, key, salt)
            assert ArchiveDAO.detect_format(legacy_path) == "encrypted_v1"

            # Non-existent file
            assert ArchiveDAO.detect_format(Path(tmpdir) / "nonexistent") == "new_file"


class TestAssetCache:
    """Tests for the AssetCache"""

    def test_populate_from_assets(self):
        """Test populating cache from asset index"""
        assets = AssetIndex()
        asset = Asset.create(AssetType.IMAGE, "image/png", b"test data")
        assets.add(asset)

        cache = AssetCache()
        cache.populate_from_assets(assets)

        assert asset.asset_id in cache
        assert cache.get_asset_bytes(asset.asset_id) == b"test data"

    def test_incremental_save_reuses_bytes(self):
        """Test that incremental saves reuse unchanged asset bytes"""
        notebook = Notebook()
        page = Page()
        image = Image(
            position=Point(0, 0, 1),
            width=100,
            height=100,
            asset_id="test_asset",
        )
        page.add_element(image)
        notebook.pages.append(page)

        assets = AssetIndex()
        asset = Asset(
            asset_id="test_asset",
            asset_type=AssetType.IMAGE,
            mime_type="image/png",
            data=b"original data",
        )
        assets.add(asset)

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test.denc"
            salt = SecureEncryption.generate_salt()
            key = SecureEncryption.derive_key("testpass", salt)

            # First save
            _save_single(notebook, assets, filepath, key, salt)

            # Cache the asset bytes
            cache = AssetCache()
            cache.populate_from_assets(assets)
            previous_bytes = cache.get_all_bytes()

            # Second save with cache (should reuse bytes)
            _save_single(
                notebook,
                assets,
                filepath,
                key,
                salt,
                previous_asset_bytes=previous_bytes,
            )

            # Verify file still loads correctly
            loaded_notebook, loaded_assets = _load_single(filepath, key)
            assert loaded_assets.get("test_asset").data == b"original data"


class TestMigration:
    """Tests for migration from legacy to archive format"""

    def test_migrate_notebook_with_inline_image(self):
        """Test migrating notebook with inline image data"""
        notebook = Notebook()
        page = Page()

        # Image with inline data (legacy style)
        image_data = b"\x89PNG\r\n\x1a\n" + b"inline image" * 10
        image = Image(
            position=Point(0, 0, 1),
            width=100,
            height=100,
            image_data=image_data,
        )
        page.add_element(image)
        notebook.pages.append(page)

        with tempfile.TemporaryDirectory() as tmpdir:
            legacy_path = Path(tmpdir) / "legacy.enc"
            archive_path = Path(tmpdir) / "archive.denc"
            salt = SecureEncryption.generate_salt()
            key = SecureEncryption.derive_key("testpass", salt)

            # Save in legacy format
            _write_legacy_notebook(notebook, legacy_path, key, salt)

            # Migrate
            migrated_notebook, assets = ArchiveMigration.migrate_notebook(
                legacy_path, archive_path, key, salt
            )

            # Verify migration
            migrated_image = migrated_notebook.pages[0].elements[0]
            assert isinstance(migrated_image, Image)
            assert migrated_image.asset_id is not None
            assert migrated_image.image_data is None  # Inline data cleared

            # Verify asset created
            assert len(assets) == 1
            asset = assets.get(migrated_image.asset_id)
            assert asset.data == image_data

    def test_inject_asset_data(self):
        """Test injecting asset data back into elements"""
        notebook = Notebook()
        page = Page()
        image = Image(
            position=Point(0, 0, 1),
            width=100,
            height=100,
            asset_id="test_asset",
        )
        page.add_element(image)
        notebook.pages.append(page)

        assets = AssetIndex()
        asset = Asset(
            asset_id="test_asset",
            asset_type=AssetType.IMAGE,
            mime_type="image/png",
            data=b"test data",
        )
        assets.add(asset)

        # Before injection
        assert image.image_data is None

        # Inject
        ArchiveMigration.inject_asset_data(notebook, assets)

        # After injection
        assert image.image_data == b"test data"


class TestMimeTypeDetection:
    """Tests for MIME type detection functions"""

    def test_detect_png(self):
        assert detect_image_mime_type(b"\x89PNG\r\n\x1a\n") == "image/png"

    def test_detect_jpeg(self):
        assert detect_image_mime_type(b"\xff\xd8\xff\xe0") == "image/jpeg"

    def test_detect_gif(self):
        assert detect_image_mime_type(b"GIF89a") == "image/gif"

    def test_detect_wav(self):
        assert detect_audio_mime_type(b"RIFF\x00\x00\x00\x00WAVE") == "audio/wav"

    def test_detect_mp3(self):
        assert detect_audio_mime_type(b"ID3\x04\x00") == "audio/mpeg"

    def test_detect_mp4(self):
        data = b"\x00\x00\x00\x1cftypisom\x00\x00\x00\x00"
        assert detect_video_mime_type(data) == "video/mp4"

    def test_detect_avi(self):
        data = b"RIFF\x00\x00\x00\x00AVI "
        assert detect_video_mime_type(data) == "video/x-msvideo"


class TestVideoElement:
    """Tests for the Video element"""

    def test_video_serialization(self):
        """Test Video serialization round-trip"""
        video = Video(
            position=Point(10, 20, 1),
            width=320,
            height=240,
            asset_id="video_123",
            rotation=90.0,
            duration=30.5,
            thumbnail_asset_id="thumb_456",
        )

        data = video.to_dict()
        restored = Video.from_dict(data)

        assert restored.position.x == 10
        assert restored.position.y == 20
        assert restored.width == 320
        assert restored.height == 240
        assert restored.asset_id == "video_123"
        assert restored.rotation == 90.0
        assert restored.duration == 30.5
        assert restored.thumbnail_asset_id == "thumb_456"

    def test_video_equality(self):
        """Test Video equality comparison"""
        video1 = Video(
            position=Point(0, 0, 1),
            width=320,
            height=240,
            asset_id="test",
            element_id="same_id",
        )
        video2 = Video(
            position=Point(0, 0, 1),
            width=320,
            height=240,
            asset_id="test",
            element_id="same_id",
        )
        video3 = Video(
            position=Point(0, 0, 1),
            width=320,
            height=240,
            asset_id="different",
            element_id="same_id",
        )

        assert video1 == video2
        # Same element_id means they're equal (fast path)
        assert video1 == video3


class TestAutoMigration:
    """Tests for automatic migration from legacy to archive format"""

    def test_auto_migrate_on_load(self):
        """Test that legacy files are auto-migrated when loaded"""
        notebook = Notebook()
        page = Page()

        # Image with inline data (legacy style)
        image_data = b"\x89PNG\r\n\x1a\n" + b"test image" * 10
        image = Image(
            position=Point(0, 0, 1),
            width=100,
            height=100,
            image_data=image_data,
        )
        page.add_element(image)
        notebook.pages.append(page)

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test.enc"
            salt = SecureEncryption.generate_salt()
            key = SecureEncryption.derive_key("testpass", salt)

            # Save in legacy format
            _write_legacy_notebook(notebook, filepath, key, salt)
            assert ArchiveDAO.detect_format(filepath) == "encrypted_v1"

            # Migrate with archive format
            loaded, assets_by_notebook = ArchiveMigration.migrate_notebooks(
                filepath, filepath, key, salt
            )
            for notebook in loaded:
                assets = assets_by_notebook.get(notebook.notebook_id)
                if assets:
                    ArchiveMigration.inject_asset_data(notebook, assets)

            # File should now be archive format
            assert ArchiveDAO.detect_format(filepath) == "archive_v2"

            # Image should still have data (injected from assets)
            loaded_image = loaded[0].pages[0].elements[0]
            assert isinstance(loaded_image, Image)
            assert loaded_image.image_data == image_data

    def test_load_archive_format_directly(self):
        """Test loading archive format without migration"""
        notebook = Notebook()
        page = Page()
        image = Image(
            position=Point(0, 0, 1),
            width=100,
            height=100,
            asset_id="test_asset",
        )
        page.add_element(image)
        notebook.pages.append(page)

        assets = AssetIndex()
        asset = Asset(
            asset_id="test_asset",
            asset_type=AssetType.IMAGE,
            mime_type="image/png",
            data=b"test data",
        )
        assets.add(asset)

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test.denc"
            salt = SecureEncryption.generate_salt()
            key = SecureEncryption.derive_key("testpass", salt)

            # Save in archive format
            _save_single(notebook, assets, filepath, key, salt)

            # Load from archive format
            loaded, assets_by_notebook = ArchiveDAO.load_all(filepath, key)
            for notebook in loaded:
                assets = assets_by_notebook.get(notebook.notebook_id)
                if assets:
                    ArchiveMigration.inject_asset_data(notebook, assets)

            # Image should have data injected
            loaded_image = loaded[0].pages[0].elements[0]
            assert isinstance(loaded_image, Image)
            assert loaded_image.image_data == b"test data"


class TestUnencryptedExport:
    """Tests for unencrypted archive export/import"""

    def test_export_and_import_zip(self):
        """Test exporting and importing unencrypted ZIP archive"""
        notebook = Notebook()
        page = Page()

        stroke = Stroke(
            points=[Point(0, 0, 1), Point(10, 10, 1)],
            color="black",
            size=2.0,
            tool="pen",
        )
        page.add_element(stroke)

        image = Image(
            position=Point(50, 50, 1),
            width=100,
            height=100,
            asset_id="img_123",
        )
        page.add_element(image)
        notebook.pages.append(page)

        assets = AssetIndex()
        asset = Asset(
            asset_id="img_123",
            asset_type=AssetType.IMAGE,
            mime_type="image/png",
            data=b"\x89PNG\r\n\x1a\n" + b"test image data",
        )
        assets.add(asset)

        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = Path(tmpdir) / "export.zip"

            # Export
            ArchiveDAO.export_unencrypted(notebook, assets, zip_path, format="zip")
            assert zip_path.exists()

            # Verify it's a valid ZIP
            import zipfile

            assert zipfile.is_zipfile(zip_path)

            # Check contents
            with zipfile.ZipFile(zip_path, "r") as zf:
                names = zf.namelist()
                assert "manifest.json" in names
                assert any(n.startswith("pages/") for n in names)
                assert any(n.startswith("assets/") for n in names)

            # Import
            imported_notebook, imported_assets = ArchiveDAO.import_unencrypted(zip_path)

            assert imported_notebook.notebook_id == notebook.notebook_id
            assert len(imported_notebook.pages) == 1
            assert len(imported_notebook.pages[0].elements) == 2
            assert len(imported_assets) == 1
            assert imported_assets.get("img_123").data == asset.data

    def test_export_and_import_tar(self):
        """Test exporting and importing unencrypted TAR archive"""
        notebook = Notebook()
        page = Page()
        page.add_element(
            Stroke(
                points=[Point(0, 0, 1)],
                color="red",
                size=1.0,
                tool="pen",
            )
        )
        notebook.pages.append(page)

        assets = AssetIndex()

        with tempfile.TemporaryDirectory() as tmpdir:
            tar_path = Path(tmpdir) / "export.tar.gz"

            # Export
            ArchiveDAO.export_unencrypted(notebook, assets, tar_path, format="tar")
            assert tar_path.exists()

            # Import
            imported_notebook, _ = ArchiveDAO.import_unencrypted(tar_path)

            assert imported_notebook.notebook_id == notebook.notebook_id
            assert len(imported_notebook.pages) == 1

    def test_assets_have_proper_extensions(self):
        """Test that exported assets have proper file extensions"""
        notebook = Notebook()
        notebook.pages.append(Page())

        assets = AssetIndex()
        assets.add(
            Asset(
                asset_id="img1",
                asset_type=AssetType.IMAGE,
                mime_type="image/png",
                data=b"png data",
            )
        )
        assets.add(
            Asset(
                asset_id="vid1",
                asset_type=AssetType.VIDEO,
                mime_type="video/mp4",
                data=b"mp4 data",
            )
        )
        assets.add(
            Asset(
                asset_id="aud1",
                asset_type=AssetType.AUDIO,
                mime_type="audio/wav",
                data=b"wav data",
            )
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = Path(tmpdir) / "export.zip"
            ArchiveDAO.export_unencrypted(notebook, assets, zip_path, format="zip")

            import zipfile

            with zipfile.ZipFile(zip_path, "r") as zf:
                names = zf.namelist()
                assert "assets/img1.png" in names
                assert "assets/vid1.mp4" in names
                assert "assets/aud1.wav" in names
