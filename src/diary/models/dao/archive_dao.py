"""Archive-based persistence for notebooks with separate asset storage"""

import io
import logging
import os
import secrets
import struct
import tarfile
import tempfile
from pathlib import Path
from typing import Callable, cast

import msgpack
import nacl.secret
import zstd

from diary.models.asset import Asset, AssetIndex, AssetType
from diary.models.manifest import ArchiveManifest
from diary.models.notebook import Notebook
from diary.models.page import Page
from diary.utils import encryption


class ArchiveDAO:
    """
    Handles reading/writing encrypted archive format.

    Archive format:
    - DIARYARC02 (magic, 10 bytes)
    - Version (2 bytes, little-endian)
    - Salt (32 bytes)
    - Encrypted chunks containing ZSTD-compressed TAR archive

    TAR structure:
    - manifest.msgpack (notebook metadata + asset index)
    - pages/{page_id}.msgpack (page data)
    - assets/{asset_id}.bin (raw binary data)
    """

    MAGIC: bytes = b"DIARYARC02"
    VERSION: int = 2
    HEADER_SIZE: int = 10 + 2 + 32  # magic + version + salt

    @staticmethod
    def save_all(
        notebooks: list[Notebook],
        assets_by_notebook: dict[str, AssetIndex],
        filepath: Path,
        key_buffer: encryption.SecureBuffer,
        salt: bytes,
        previous_asset_bytes: dict[str, dict[str, bytes]] | None = None,
        progress: Callable[[int, int], None] | None = None,
    ) -> None:
        """
        Save multiple notebooks and assets to a single encrypted archive.

        Args:
            notebooks: List of notebooks to save
            assets_by_notebook: Mapping of notebook_id to AssetIndex
            filepath: Output file path
            key_buffer: Derived encryption key
            salt: Salt for encryption header
            previous_asset_bytes: Cached asset bytes to reuse (for incremental saves)
            progress: Optional progress callback
        """
        logger = logging.getLogger("ArchiveDAO")
        logger.debug("Saving %d notebooks to archive: %s", len(notebooks), filepath)

        tar_bytes = ArchiveDAO._build_archive_multi(
            notebooks, assets_by_notebook, previous_asset_bytes
        )
        compressed = zstd.ZSTD_compress(tar_bytes, 3)
        output_data = ArchiveDAO._build_file_with_header(compressed, salt)
        ArchiveDAO._encrypt_and_write(output_data, filepath, key_buffer, salt, progress)

        logger.debug("Multi-notebook archive saved: %d bytes", len(output_data))

    @staticmethod
    def load_all(
        filepath: Path,
        key_buffer: encryption.SecureBuffer,
        progress: Callable[[int, int], None] | None = None,
    ) -> tuple[list[Notebook], dict[str, AssetIndex]]:
        """
        Load multiple notebooks and assets from encrypted archive.

        Args:
            filepath: Path to encrypted archive
            key_buffer: Derived encryption key
            progress: Optional progress callback

        Returns:
            Tuple of (list[Notebook], dict[notebook_id, AssetIndex])
        """
        logger = logging.getLogger("ArchiveDAO")
        logger.debug("Loading notebooks from archive: %s", filepath)

        if not filepath.exists():
            logger.debug("Archive does not exist, returning empty notebook list")
            return [Notebook(pages=[Page()])], {}

        compressed_tar = ArchiveDAO._read_and_decrypt(filepath, key_buffer, progress)
        tar_bytes = zstd.decompress(compressed_tar)

        (
            single_manifest,
            single_pages_data,
            single_asset_bytes,
            multi_manifests,
            multi_pages_data,
            multi_asset_bytes,
            notebook_order,
        ) = ArchiveDAO._extract_archive_entries(tar_bytes)
        pages: list[Page] = []

        if multi_manifests:
            notebooks: list[Notebook] = []
            assets_by_notebook: dict[str, AssetIndex] = {}

            for notebook_id in notebook_order:
                manifest = multi_manifests.get(notebook_id)
                if manifest is None:
                    raise ValueError(
                        f"Archive missing manifest for notebook {notebook_id}"
                    )

                pages_data = multi_pages_data.get(notebook_id, {})
                asset_bytes = multi_asset_bytes.get(notebook_id, {})
                assets = AssetIndex.from_manifest_entries(manifest.assets, asset_bytes)

                pages = []
                for page_id in manifest.page_ids:
                    if page_id in pages_data:
                        page_dict = msgpack.unpackb(pages_data[page_id], raw=False)
                        pages.append(Page.from_dict(page_dict))

                notebook = Notebook(
                    pages=pages,
                    metadata=manifest.notebook_metadata,
                    notebook_id=manifest.notebook_id,
                )
                notebooks.append(notebook)
                assets_by_notebook[notebook.notebook_id] = assets

            logger.debug("Loaded %d notebooks from multi-archive", len(notebooks))
            return notebooks, assets_by_notebook

        if single_manifest is None:
            raise ValueError("Archive missing manifest")

        assets = AssetIndex.from_manifest_entries(
            single_manifest.assets, single_asset_bytes
        )
        pages = []
        for page_id in single_manifest.page_ids:
            if page_id in single_pages_data:
                page_dict = msgpack.unpackb(single_pages_data[page_id], raw=False)
                pages.append(Page.from_dict(page_dict))

        notebook = Notebook(
            pages=pages,
            metadata=single_manifest.notebook_metadata,
            notebook_id=single_manifest.notebook_id,
        )

        logger.debug("Archive loaded: %d pages, %d assets", len(pages), len(assets))
        return [notebook], {notebook.notebook_id: assets}

    @staticmethod
    def _build_archive(
        manifest: ArchiveManifest,
        pages: list[Page],
        assets: AssetIndex,
        previous_asset_bytes: dict[str, bytes] | None = None,
    ) -> bytes:
        """Build TAR archive in memory"""
        tar_buffer = io.BytesIO()

        with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
            # Write manifest
            manifest_bytes = cast(
                bytes, msgpack.packb(manifest.to_dict(), use_bin_type=True)
            )
            ArchiveDAO._add_bytes_to_tar(tar, "manifest.msgpack", manifest_bytes)

            # Write pages
            for page in pages:
                page_bytes = cast(
                    bytes, msgpack.packb(page.to_dict(), use_bin_type=True)
                )
                ArchiveDAO._add_bytes_to_tar(
                    tar, f"pages/{page.page_id}.msgpack", page_bytes
                )

            # Write assets (reuse unchanged bytes when available)
            for asset in assets:
                if (
                    previous_asset_bytes
                    and asset.asset_id in previous_asset_bytes
                    and asset.checksum is not None
                ):
                    # Reuse cached bytes for unchanged asset
                    asset_data = previous_asset_bytes[asset.asset_id]
                else:
                    # New or modified asset
                    asset_data = asset.data or b""

                ArchiveDAO._add_bytes_to_tar(
                    tar, f"assets/{asset.asset_id}.bin", asset_data
                )

        return tar_buffer.getvalue()

    @staticmethod
    def _build_archive_multi(
        notebooks: list[Notebook],
        assets_by_notebook: dict[str, AssetIndex],
        previous_asset_bytes: dict[str, dict[str, bytes]] | None = None,
    ) -> bytes:
        """Build TAR archive with multiple notebooks in memory"""
        tar_buffer = io.BytesIO()

        with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
            for notebook in notebooks:
                assets = assets_by_notebook.get(notebook.notebook_id, AssetIndex())
                manifest = ArchiveManifest(
                    notebook_id=notebook.notebook_id,
                    notebook_metadata=dict(notebook.metadata),
                    page_ids=[page.page_id for page in notebook.pages],
                    assets=assets.to_manifest_entries(),
                )
                manifest.update_modified()

                prefix = f"notebooks/{notebook.notebook_id}"
                manifest_bytes = cast(
                    bytes, msgpack.packb(manifest.to_dict(), use_bin_type=True)
                )
                ArchiveDAO._add_bytes_to_tar(
                    tar, f"{prefix}/manifest.msgpack", manifest_bytes
                )

                for page in notebook.pages:
                    page_bytes = cast(
                        bytes, msgpack.packb(page.to_dict(), use_bin_type=True)
                    )
                    ArchiveDAO._add_bytes_to_tar(
                        tar,
                        f"{prefix}/pages/{page.page_id}.msgpack",
                        page_bytes,
                    )

                previous_bytes = None
                if (
                    previous_asset_bytes
                    and notebook.notebook_id in previous_asset_bytes
                ):
                    previous_bytes = previous_asset_bytes[notebook.notebook_id]

                for asset in assets:
                    if (
                        previous_bytes
                        and asset.asset_id in previous_bytes
                        and asset.checksum is not None
                    ):
                        asset_data = previous_bytes[asset.asset_id]
                    else:
                        asset_data = asset.data or b""

                    ArchiveDAO._add_bytes_to_tar(
                        tar, f"{prefix}/assets/{asset.asset_id}.bin", asset_data
                    )

        return tar_buffer.getvalue()

    @staticmethod
    def _extract_archive(
        tar_bytes: bytes,
    ) -> tuple[ArchiveManifest, dict[str, bytes], dict[str, bytes]]:
        """
        Extract manifest, page data, and asset data from TAR.

        Returns:
            Tuple of (manifest, page_id->page_bytes, asset_id->asset_bytes)
        """
        tar_buffer = io.BytesIO(tar_bytes)
        manifest: ArchiveManifest | None = None
        pages_data: dict[str, bytes] = {}
        asset_bytes: dict[str, bytes] = {}

        with tarfile.open(fileobj=tar_buffer, mode="r") as tar:
            for member in tar.getmembers():
                if not member.isfile():
                    continue

                file_obj = tar.extractfile(member)
                if file_obj is None:
                    continue

                data = file_obj.read()

                if member.name == "manifest.msgpack":
                    manifest_dict = msgpack.unpackb(data, raw=False)
                    manifest = ArchiveManifest.from_dict(manifest_dict)
                elif member.name.startswith("pages/") and member.name.endswith(
                    ".msgpack"
                ):
                    page_id = member.name[6:-8]  # Remove "pages/" and ".msgpack"
                    pages_data[page_id] = data
                elif member.name.startswith("assets/") and member.name.endswith(".bin"):
                    asset_id = member.name[7:-4]  # Remove "assets/" and ".bin"
                    asset_bytes[asset_id] = data

        if manifest is None:
            raise ValueError("Archive missing manifest")

        return manifest, pages_data, asset_bytes

    @staticmethod
    def _extract_archive_entries(
        tar_bytes: bytes,
    ) -> tuple[
        ArchiveManifest | None,
        dict[str, bytes],
        dict[str, bytes],
        dict[str, ArchiveManifest],
        dict[str, dict[str, bytes]],
        dict[str, dict[str, bytes]],
        list[str],
    ]:
        """
        Extract single and multi-notebook archive data from TAR.

        Returns:
            Tuple of (single_manifest, single_pages_data, single_asset_bytes,
            multi_manifests, multi_pages_data, multi_asset_bytes, notebook_order)
        """
        tar_buffer = io.BytesIO(tar_bytes)
        single_manifest: ArchiveManifest | None = None
        single_pages_data: dict[str, bytes] = {}
        single_asset_bytes: dict[str, bytes] = {}

        multi_manifests: dict[str, ArchiveManifest] = {}
        multi_pages_data: dict[str, dict[str, bytes]] = {}
        multi_asset_bytes: dict[str, dict[str, bytes]] = {}
        notebook_order: list[str] = []

        with tarfile.open(fileobj=tar_buffer, mode="r") as tar:
            for member in tar.getmembers():
                if not member.isfile():
                    continue

                file_obj = tar.extractfile(member)
                if file_obj is None:
                    continue

                data = file_obj.read()
                name = member.name

                if name == "manifest.msgpack":
                    manifest_dict = msgpack.unpackb(data, raw=False)
                    single_manifest = ArchiveManifest.from_dict(manifest_dict)
                    continue

                if name.startswith("pages/") and name.endswith(".msgpack"):
                    page_id = name[6:-8]
                    single_pages_data[page_id] = data
                    continue

                if name.startswith("assets/") and name.endswith(".bin"):
                    asset_id = name[7:-4]
                    single_asset_bytes[asset_id] = data
                    continue

                if not name.startswith("notebooks/"):
                    continue

                parts = name.split("/")
                if len(parts) < 3:
                    continue

                notebook_id = parts[1]
                if notebook_id not in notebook_order:
                    notebook_order.append(notebook_id)

                if len(parts) == 3 and parts[2] == "manifest.msgpack":
                    manifest_dict = msgpack.unpackb(data, raw=False)
                    multi_manifests[notebook_id] = ArchiveManifest.from_dict(
                        manifest_dict
                    )
                    continue

                if (
                    len(parts) >= 4
                    and parts[2] == "pages"
                    and name.endswith(".msgpack")
                ):
                    page_id = parts[3][:-8]
                    multi_pages_data.setdefault(notebook_id, {})[page_id] = data
                    continue

                if len(parts) >= 4 and parts[2] == "assets" and name.endswith(".bin"):
                    asset_id = parts[3][:-4]
                    multi_asset_bytes.setdefault(notebook_id, {})[asset_id] = data

        return (
            single_manifest,
            single_pages_data,
            single_asset_bytes,
            multi_manifests,
            multi_pages_data,
            multi_asset_bytes,
            notebook_order,
        )

    @staticmethod
    def _add_bytes_to_tar(tar: tarfile.TarFile, name: str, data: bytes) -> None:
        """Add bytes to a TAR archive as a file"""
        info = tarfile.TarInfo(name=name)
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))

    @staticmethod
    def _build_file_with_header(compressed_data: bytes, salt: bytes) -> bytes:
        """Build the raw file bytes with our custom header"""
        header = ArchiveDAO.MAGIC + struct.pack("<H", ArchiveDAO.VERSION) + salt
        return header + compressed_data

    @staticmethod
    def _encrypt_and_write(
        data: bytes,
        filepath: Path,
        key_buffer: encryption.SecureBuffer,
        salt: bytes,
        progress: Callable[[int, int], None] | None = None,
    ) -> None:
        """Encrypt data and write to file using the existing encryption system"""
        # We reuse the SecureEncryption class but with our own header
        # The data already contains our header (DIARYARC02), so we need to
        # extract just the payload for encryption

        # Extract payload (skip our header)
        payload = data[ArchiveDAO.HEADER_SIZE :]

        # Use the existing encryption but write our header first
        output_path = Path(filepath)
        output_dir = output_path.parent
        total_size = len(payload)
        bytes_processed = 0

        box = nacl.secret.Aead(bytes(key_buffer))

        with tempfile.NamedTemporaryFile(
            suffix=".tmp", dir=output_dir, delete=False
        ) as temp_file:
            temp_path = temp_file.name

            try:
                # Write OUR header (DIARYARC02 + version + salt)
                _ = temp_file.write(ArchiveDAO.MAGIC)
                _ = temp_file.write(struct.pack("<H", ArchiveDAO.VERSION))
                _ = temp_file.write(salt)

                # Encrypt payload in chunks
                chunk_number = 0
                offset = 0
                chunk_size = encryption.SecureEncryption.CHUNK_SIZE

                while offset < total_size:
                    chunk_end = min(offset + chunk_size, total_size)
                    chunk = payload[offset:chunk_end]

                    # Generate nonce
                    nonce_base = secrets.token_bytes(
                        encryption.SecureEncryption.NONCE_SIZE - 8
                    )
                    nonce = nonce_base + struct.pack("<Q", chunk_number)

                    # Encrypt
                    encrypted_chunk = box.encrypt(chunk, nonce=nonce)

                    # Write chunk size + encrypted data
                    _ = temp_file.write(struct.pack("<I", len(encrypted_chunk)))
                    _ = temp_file.write(encrypted_chunk)

                    bytes_processed += len(chunk)
                    offset = chunk_end
                    chunk_number += 1

                    if progress:
                        progress(bytes_processed, total_size)

                temp_file.flush()
                os.fsync(temp_file.fileno())

            except Exception:
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass
                raise

        # Atomic move
        try:
            if output_path.exists():
                os.unlink(output_path)
            os.rename(temp_path, output_path)
        except (IOError, OSError):
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise

    @staticmethod
    def _read_and_decrypt(
        filepath: Path,
        key_buffer: encryption.SecureBuffer,
        progress: Callable[[int, int], None] | None = None,
    ) -> bytes:
        """Read file, verify header, and decrypt payload"""
        import nacl.secret

        logger = logging.getLogger("ArchiveDAO")

        with open(filepath, "rb") as f:
            # Read and verify header
            magic = f.read(len(ArchiveDAO.MAGIC))
            if magic != ArchiveDAO.MAGIC:
                raise ValueError(f"Invalid archive format: wrong magic bytes {magic!r}")

            version_bytes = f.read(2)
            version = struct.unpack("<H", version_bytes)[0]
            if version != ArchiveDAO.VERSION:
                raise ValueError(f"Unsupported archive version: {version}")

            salt = f.read(encryption.SecureEncryption.SALT_SIZE)
            if len(salt) != encryption.SecureEncryption.SALT_SIZE:
                raise ValueError("Invalid archive: truncated salt")

            # Decrypt chunks
            file_size = filepath.stat().st_size
            bytes_processed = ArchiveDAO.HEADER_SIZE
            decrypted_chunks: list[bytes] = []

            box = nacl.secret.Aead(bytes(key_buffer))

            while True:
                chunk_size_bytes = f.read(4)
                if not chunk_size_bytes:
                    break

                if len(chunk_size_bytes) < 4:
                    raise ValueError("Invalid archive: truncated chunk size")

                chunk_size = struct.unpack("<I", chunk_size_bytes)[0]

                # Sanity check
                max_chunk = (
                    encryption.SecureEncryption.CHUNK_SIZE
                    + encryption.SecureEncryption.NONCE_SIZE
                    + encryption.SecureEncryption.TAG_SIZE
                    + 100
                )
                if chunk_size > max_chunk:
                    raise ValueError(f"Invalid archive: chunk too large ({chunk_size})")

                encrypted_chunk = f.read(chunk_size)
                if len(encrypted_chunk) != chunk_size:
                    raise ValueError("Invalid archive: truncated chunk")

                try:
                    plaintext = box.decrypt(encrypted_chunk)
                    decrypted_chunks.append(plaintext)
                except Exception as e:
                    logger.error("Decryption failed: %s", e)
                    raise ValueError(
                        "Decryption failed: wrong password or corrupted data"
                    ) from e

                bytes_processed += 4 + chunk_size
                if progress:
                    progress(bytes_processed, file_size)

        return b"".join(decrypted_chunks)

    @staticmethod
    def read_salt_from_file(filepath: Path) -> bytes:
        """Read salt from archive file header"""
        with open(filepath, "rb") as f:
            magic = f.read(len(ArchiveDAO.MAGIC))
            if magic != ArchiveDAO.MAGIC:
                raise ValueError(f"Invalid archive format: wrong magic bytes {magic!r}")

            version_bytes = f.read(2)
            version = struct.unpack("<H", version_bytes)[0]
            if version != ArchiveDAO.VERSION:
                raise ValueError(f"Unsupported archive version: {version}")

            salt = f.read(encryption.SecureEncryption.SALT_SIZE)
            if len(salt) != encryption.SecureEncryption.SALT_SIZE:
                raise ValueError("Invalid archive: truncated salt")

            return salt

    @staticmethod
    def detect_format(filepath: Path) -> str:
        """
        Detect file format from magic bytes.

        Returns:
            "archive_v2" for new archive format
            "encrypted_v1" for legacy encrypted format

        Raises:
            ValueError for unknown formats
        """
        if not filepath.exists():
            return "new_file"

        with open(filepath, "rb") as f:
            magic = f.read(10)

            if magic == ArchiveDAO.MAGIC:
                return "archive_v2"
            if magic[:8] == encryption.SecureEncryption.MAGIC:
                return "encrypted_v1"

            raise ValueError(f"Unknown file format: {magic!r}")

    @staticmethod
    def export_unencrypted(
        notebook: Notebook,
        assets: AssetIndex,
        filepath: Path,
        format: str = "zip",
    ) -> None:
        """
        Export notebook and assets to an unencrypted archive.

        This creates a standard archive that can be opened with 7zip, WinRAR, etc.

        Args:
            notebook: The notebook to export
            assets: Index of binary assets
            filepath: Output file path (.zip or .tar)
            format: Archive format - "zip" (default) or "tar"
        """
        import zipfile

        logger = logging.getLogger("ArchiveDAO")
        logger.info("Exporting unencrypted archive to %s", filepath)

        # Build manifest
        manifest = ArchiveManifest(
            notebook_id=notebook.notebook_id,
            notebook_metadata=dict(notebook.metadata),
            page_ids=[page.page_id for page in notebook.pages],
            assets=assets.to_manifest_entries(),
        )
        manifest.update_modified()

        if format == "zip":
            with zipfile.ZipFile(filepath, "w", zipfile.ZIP_DEFLATED) as zf:
                # Write manifest as JSON (human-readable)
                import json

                manifest_json = json.dumps(manifest.to_dict(), indent=2)
                zf.writestr("manifest.json", manifest_json)

                # Write pages as JSON
                for page in notebook.pages:
                    page_json = json.dumps(page.to_dict(), indent=2)
                    zf.writestr(f"pages/{page.page_id}.json", page_json)

                # Write assets as raw binary with proper extensions
                for asset in assets:
                    ext = ArchiveDAO._get_extension_for_mime(asset.mime_type)
                    if asset.data:
                        zf.writestr(f"assets/{asset.asset_id}{ext}", asset.data)

        elif format == "tar":
            with tarfile.open(filepath, "w:gz") as tar:
                # Write manifest
                import json

                manifest_json = json.dumps(manifest.to_dict(), indent=2).encode()
                ArchiveDAO._add_bytes_to_tar(tar, "manifest.json", manifest_json)

                # Write pages
                for page in notebook.pages:
                    page_json = json.dumps(page.to_dict(), indent=2).encode()
                    ArchiveDAO._add_bytes_to_tar(
                        tar, f"pages/{page.page_id}.json", page_json
                    )

                # Write assets
                for asset in assets:
                    ext = ArchiveDAO._get_extension_for_mime(asset.mime_type)
                    if asset.data:
                        ArchiveDAO._add_bytes_to_tar(
                            tar, f"assets/{asset.asset_id}{ext}", asset.data
                        )
        else:
            raise ValueError(f"Unsupported format: {format}")

        logger.info(
            "Export completed: %d pages, %d assets", len(notebook.pages), len(assets)
        )

    @staticmethod
    def import_unencrypted(filepath: Path) -> tuple[Notebook, AssetIndex]:
        """
        Import notebook and assets from an unencrypted archive.

        Args:
            filepath: Path to unencrypted archive (.zip or .tar.gz)

        Returns:
            Tuple of (Notebook, AssetIndex)
        """
        import json
        import zipfile

        logger = logging.getLogger("ArchiveDAO")
        logger.info("Importing unencrypted archive from %s", filepath)

        manifest: ArchiveManifest | None = None
        pages_data: dict[str, dict[str, Page]] = {}
        asset_bytes: dict[str, bytes] = {}
        asset_mimes: dict[str, str] = {}

        if zipfile.is_zipfile(filepath):
            with zipfile.ZipFile(filepath, "r") as zf:
                for name in zf.namelist():
                    if name == "manifest.json":
                        manifest_dict = json.loads(zf.read(name))
                        manifest = ArchiveManifest.from_dict(manifest_dict)
                    elif name.startswith("pages/") and name.endswith(".json"):
                        page_id = name[6:-5]  # Remove "pages/" and ".json"
                        pages_data[page_id] = json.loads(zf.read(name))
                    elif name.startswith("assets/"):
                        # Extract asset ID (remove "assets/" prefix and extension)
                        asset_filename = name[7:]
                        asset_id = asset_filename.rsplit(".", 1)[0]
                        asset_bytes[asset_id] = zf.read(name)
                        # Guess mime from extension
                        asset_mimes[asset_id] = ArchiveDAO._get_mime_for_extension(
                            "." + asset_filename.rsplit(".", 1)[-1]
                            if "." in asset_filename
                            else ""
                        )
        else:
            # Try TAR
            with tarfile.open(filepath, "r:*") as tar:
                for member in tar.getmembers():
                    if not member.isfile():
                        continue
                    file_obj = tar.extractfile(member)
                    if file_obj is None:
                        continue
                    data = file_obj.read()

                    if member.name == "manifest.json":
                        manifest_dict = json.loads(data)
                        manifest = ArchiveManifest.from_dict(manifest_dict)
                    elif member.name.startswith("pages/") and member.name.endswith(
                        ".json"
                    ):
                        page_id = member.name[6:-5]
                        pages_data[page_id] = json.loads(data)
                    elif member.name.startswith("assets/"):
                        asset_filename = member.name[7:]
                        asset_id = asset_filename.rsplit(".", 1)[0]
                        asset_bytes[asset_id] = data
                        asset_mimes[asset_id] = ArchiveDAO._get_mime_for_extension(
                            "." + asset_filename.rsplit(".", 1)[-1]
                            if "." in asset_filename
                            else ""
                        )

        if manifest is None:
            raise ValueError("Archive missing manifest.json")

        # Build asset index from manifest + loaded bytes
        assets = AssetIndex()
        for entry in manifest.assets:
            asset_id = entry["aid"]
            data = asset_bytes.get(asset_id)
            # Use mime from manifest if available, otherwise guess from extension
            mime = entry.get("mime") or asset_mimes.get(
                asset_id, "application/octet-stream"
            )
            asset = Asset(
                asset_id=asset_id,
                asset_type=AssetType(entry["atype"]),
                mime_type=mime,
                data=data,
                checksum=entry.get("csum"),
            )
            assets.add(asset)

        # Build pages
        pages = []
        for page_id in manifest.page_ids:
            if page_id in pages_data:
                page = Page.from_dict(pages_data[page_id])
                pages.append(page)

        # Build notebook
        notebook = Notebook(
            pages=pages,
            metadata=manifest.notebook_metadata,
            notebook_id=manifest.notebook_id,
        )

        logger.info("Import completed: %d pages, %d assets", len(pages), len(assets))
        return notebook, assets

    @staticmethod
    def _get_extension_for_mime(mime_type: str) -> str:
        """Get file extension for MIME type"""
        mime_to_ext = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/gif": ".gif",
            "image/webp": ".webp",
            "audio/wav": ".wav",
            "audio/mpeg": ".mp3",
            "audio/flac": ".flac",
            "audio/ogg": ".ogg",
            "video/mp4": ".mp4",
            "video/webm": ".webm",
            "video/quicktime": ".mov",
            "video/x-msvideo": ".avi",
            "video/x-matroska": ".mkv",
        }
        return mime_to_ext.get(mime_type, ".bin")

    @staticmethod
    def _get_mime_for_extension(ext: str) -> str:
        """Get MIME type for file extension"""
        ext_to_mime = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".wav": "audio/wav",
            ".mp3": "audio/mpeg",
            ".flac": "audio/flac",
            ".ogg": "audio/ogg",
            ".mp4": "video/mp4",
            ".webm": "video/webm",
            ".mov": "video/quicktime",
            ".avi": "video/x-msvideo",
            ".mkv": "video/x-matroska",
        }
        return ext_to_mime.get(ext.lower(), "application/octet-stream")
