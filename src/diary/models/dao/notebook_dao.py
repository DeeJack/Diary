"""Methods to save and load the Notebook"""

import json
import logging
from pathlib import Path
from typing import Callable, cast

import msgpack
import zstd

from diary.models.asset import AssetIndex
from diary.models.notebook import Notebook
from diary.models.page import Page
from diary.utils import encryption

# Magic bytes for format detection
ARCHIVE_MAGIC = b"DIARYARC02"
LEGACY_MAGIC = b"SECENC01"


class NotebookDAO:
    """Contains methods to save and load the Notebook"""

    @staticmethod
    def save(
        notebook: Notebook,
        filepath: Path,
        password: encryption.SecureBuffer,
        salt: bytes,
        progress: Callable[[int, int], None] | None = None,
    ) -> None:
        """Saves the encrypted Notebook using the derived password"""
        notebook_encoded: bytes = cast(
            bytes, msgpack.packb(notebook.to_dict(), use_bin_type=True)
        )
        compressed_notebook = zstd.ZSTD_compress(notebook_encoded, 3)

        logging.getLogger("NotebookDAO").debug("Encrypting and saving the notebook")
        encryption.SecureEncryption.encrypt_bytes_to_file(
            compressed_notebook, filepath, password, salt, progress
        )

    @staticmethod
    def save_unencrypted(
        notebook: Notebook,
        filepath: Path,
    ) -> None:
        """Save notebook to unencrypted JSON file (for testing only)"""
        logging.getLogger("NotebookDAO").debug("Num pages: %d", len(notebook.pages))
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(notebook.to_dict(), f, indent=2)

    @staticmethod
    def load(
        filepath: Path,
        key_buffer: encryption.SecureBuffer,
        progress: Callable[[int, int], None] | None = None,
        salt: bytes | None = None,
        auto_migrate: bool = True,
    ) -> Notebook:
        """
        Loads the Notebook using the derived key, or returns an empty one.

        Auto-detects format and migrates legacy files to archive format.

        Args:
            filepath: Path to the notebook file
            key_buffer: Derived encryption key
            progress: Optional progress callback
            salt: Salt for encryption (required for auto-migration)
            auto_migrate: If True, automatically migrate legacy files to archive format
        """
        logger = logging.getLogger("NotebookDAO")

        if not filepath.exists():
            logger.debug("Notebook does not exist, returning a new notebook")
            return Notebook(pages=[Page()])

        file_format = NotebookDAO.detect_format(filepath)
        logger.debug("Detected format: %s", file_format)

        if file_format == "archive_v2":
            # Load from archive format
            from diary.models.dao.archive_dao import ArchiveDAO
            from diary.models.dao.migration import ArchiveMigration

            notebook, assets = ArchiveDAO.load(filepath, key_buffer, progress)
            # Inject asset data into elements so they have image_data populated
            ArchiveMigration.inject_asset_data(notebook, assets)
            return notebook

        # Legacy format - load and optionally migrate
        logger.debug("Loading legacy format")
        notebook_data = encryption.SecureEncryption.decrypt_file(
            filepath, key_buffer, progress
        )
        uncompressed_notebook = zstd.decompress(notebook_data)
        notebook_unpacked = cast(
            dict[str, str], msgpack.unpackb(uncompressed_notebook, raw=False)
        )
        notebook = Notebook.from_dict(notebook_unpacked)
        logger.debug("Legacy decryption completed successfully!")

        # Auto-migrate to archive format
        if auto_migrate and salt is not None:
            logger.info("Auto-migrating legacy file to archive format")
            from diary.models.dao.migration import ArchiveMigration

            try:
                migrated_notebook, assets = ArchiveMigration.migrate_notebook(
                    filepath, filepath, key_buffer, salt, progress
                )
                # Inject asset data back so elements have image_data
                ArchiveMigration.inject_asset_data(migrated_notebook, assets)
                logger.info("Migration completed successfully")
                return migrated_notebook
            except Exception as e:
                logger.warning("Auto-migration failed, using legacy data: %s", e)
                return notebook

        return notebook

    @staticmethod
    def load_unencrypted(
        filepath: Path,
    ) -> Notebook:
        """Load notebook from unencrypted JSON file (for testing only)"""
        if not filepath.exists():
            return Notebook(pages=[Page()])

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)  # pyright: ignore[reportAny]
            return Notebook.from_dict(data)  # pyright: ignore[reportAny]

    @staticmethod
    def saves(
        notebooks: list[Notebook],
        filepath: Path,
        password: encryption.SecureBuffer,
        salt: bytes,
        progress: Callable[[int, int], None] | None = None,
    ) -> None:
        """Saves the encrypted list of Notebooks using the derived password"""
        from diary.models.dao.archive_dao import ArchiveDAO
        from diary.models.dao.migration import ArchiveMigration

        assets_by_notebook: dict[str, AssetIndex] = {}
        for notebook in notebooks:
            assets_by_notebook[notebook.notebook_id] = (
                ArchiveMigration.extract_assets_from_notebook(notebook)
            )

        logging.getLogger("NotebookDAO").debug(
            "Saving %s notebooks using archive format", len(notebooks)
        )
        ArchiveDAO.save_all(
            notebooks, assets_by_notebook, filepath, password, salt, None, progress
        )

    @staticmethod
    def saves_unencrypted(
        notebooks: list[Notebook],
        filepath: Path,
    ) -> None:
        """Save list of notebooks to unencrypted JSON file (for testing only)"""
        notebooks_data = [notebook.to_dict() for notebook in notebooks]
        logging.getLogger("NotebookDAO").debug("Num notebooks: %d", len(notebooks))
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(notebooks_data, f, indent=2)

    @staticmethod
    def loads(
        filepath: Path,
        key_buffer: encryption.SecureBuffer,
        progress: Callable[[int, int], None] | None = None,
        salt: bytes | None = None,
        auto_migrate: bool = True,
    ) -> list[Notebook]:
        """Loads the list of Notebooks using the derived key, or returns an empty list"""
        if not filepath.exists():
            logging.getLogger("NotebookDAO").debug(
                "Notebooks file does not exist, returning empty list"
            )
            return [Notebook([Page()])]  # Return one notebook with one page

        file_format = NotebookDAO.detect_format(filepath)
        logging.getLogger("NotebookDAO").debug("Detected format: %s", file_format)

        if file_format == "archive_v2":
            from diary.models.dao.archive_dao import ArchiveDAO
            from diary.models.dao.migration import ArchiveMigration

            notebooks, assets_by_notebook = ArchiveDAO.load_all(
                filepath, key_buffer, progress
            )
            for notebook in notebooks:
                assets = assets_by_notebook.get(notebook.notebook_id)
                if assets:
                    ArchiveMigration.inject_asset_data(notebook, assets)
            return notebooks

        logging.getLogger("NotebookDAO").debug("Notebooks file exists, decrypting")
        notebooks_data = encryption.SecureEncryption.decrypt_file(
            filepath, key_buffer, progress
        )
        uncompressed_notebooks = zstd.decompress(notebooks_data)
        notebooks_unpacked = cast(
            list[dict[str, str]], msgpack.unpackb(uncompressed_notebooks, raw=False)
        )
        logging.getLogger("NotebookDAO").debug(
            "Decryption completed successfully! %s notebooks found",
            len(notebooks_unpacked),
        )
        notebooks = [
            Notebook.from_dict(notebook_dict) for notebook_dict in notebooks_unpacked
        ]

        if auto_migrate:
            from diary.models.dao.migration import ArchiveMigration

            try:
                if salt is None:
                    salt = encryption.SecureEncryption.read_salt_from_file(filepath)
                migrated_notebooks, assets_by_notebook = (
                    ArchiveMigration.migrate_notebooks(
                        filepath, filepath, key_buffer, salt, progress
                    )
                )
                for notebook in migrated_notebooks:
                    assets = assets_by_notebook.get(notebook.notebook_id)
                    if assets:
                        ArchiveMigration.inject_asset_data(notebook, assets)
                return migrated_notebooks
            except Exception as e:
                logging.getLogger("NotebookDAO").warning(
                    "Auto-migration failed, using legacy data: %s", e
                )

        return notebooks

    @staticmethod
    def loads_unencrypted(
        filepath: Path,
    ) -> list[Notebook]:
        """Load list of notebooks from unencrypted JSON file (for testing only)"""
        if not filepath.exists():
            return []

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)  # pyright: ignore[reportAny]
            return [Notebook.from_dict(notebook_dict) for notebook_dict in data]  # pyright: ignore[reportAny]

    @staticmethod
    def detect_format(filepath: Path) -> str:
        """
        Detect file format from magic bytes.

        Returns:
            "archive_v2" - New archive format (DIARYARC02)
            "encrypted_v1" - Legacy encrypted format (SECENC01)
            "new_file" - File does not exist

        Raises:
            ValueError for unknown formats
        """
        if not filepath.exists():
            return "new_file"

        with open(filepath, "rb") as f:
            magic = f.read(10)

            if magic == ARCHIVE_MAGIC:
                return "archive_v2"
            if magic[:8] == LEGACY_MAGIC:
                return "encrypted_v1"

            raise ValueError(f"Unknown file format: {magic!r}")

    @staticmethod
    def read_salt(filepath: Path) -> bytes:
        """
        Read salt from file header, detecting format automatically.

        Args:
            filepath: Path to encrypted file

        Returns:
            Salt bytes

        Raises:
            ValueError for unknown formats or invalid files
        """
        file_format = NotebookDAO.detect_format(filepath)

        if file_format == "new_file":
            raise FileNotFoundError(f"File does not exist: {filepath}")

        if file_format == "archive_v2":
            from diary.models.dao.archive_dao import ArchiveDAO

            return ArchiveDAO.read_salt_from_file(filepath)

        # Legacy format
        return encryption.SecureEncryption.read_salt_from_file(filepath)
