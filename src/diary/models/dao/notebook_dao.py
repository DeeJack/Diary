"""Methods to save and load the Notebook"""

import json
import logging
from pathlib import Path
from typing import Callable, cast

import msgpack
import zstd

from diary.models.notebook import Notebook
from diary.models.page import Page
from diary.utils import encryption


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
    ) -> Notebook:
        """Loads the Notebook using the derived key, or returns an empty one"""
        if not filepath.exists():
            logging.getLogger("NotebookDAO").debug(
                "Notebook does not exists, returning a new notebook"
            )
            return Notebook(pages=[Page()])

        logging.getLogger("NotebookDAO").debug("Notebook exists, decrypting")
        notebook_data = encryption.SecureEncryption.decrypt_file(
            filepath, key_buffer, progress
        )
        uncompressed_notebook = zstd.decompress(notebook_data)
        notebook_unpacked = cast(
            dict[str, str], msgpack.unpackb(uncompressed_notebook, raw=False)
        )
        logging.getLogger("NotebookDAO").debug("Decryption completed successfully!")
        return Notebook.from_dict(notebook_unpacked)

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
        notebooks_data = [notebook.to_dict() for notebook in notebooks]
        notebooks_encoded: bytes = cast(
            bytes, msgpack.packb(notebooks_data, use_bin_type=True)
        )
        compressed_notebooks = zstd.ZSTD_compress(notebooks_encoded, 3)

        logging.getLogger("NotebookDAO").debug(
            "Encrypting and saving the notebooks list, with %s notebooks",
            len(notebooks),
        )
        encryption.SecureEncryption.encrypt_bytes_to_file(
            compressed_notebooks, filepath, password, salt, progress
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
    ) -> list[Notebook]:
        """Loads the list of Notebooks using the derived key, or returns an empty list"""
        if not filepath.exists():
            logging.getLogger("NotebookDAO").debug(
                "Notebooks file does not exist, returning empty list"
            )
            return [Notebook([Page()])]  # Return one notebook with one page

        logging.getLogger("NotebookDAO").debug("Notebooks file exists, decrypting")
        notebooks_data = encryption.SecureEncryption.decrypt_file(
            filepath, key_buffer, progress
        )
        uncompressed_notebooks = zstd.decompress(notebooks_data)
        notebooks_unpacked = cast(
            list[dict[str, str]], msgpack.unpackb(uncompressed_notebooks, raw=False)
        )
        logging.getLogger("NotebookDAO").debug(
            "Decryption completed successfully! %s notebooks found", notebooks_unpacked
        )
        return [
            Notebook.from_dict(notebook_dict) for notebook_dict in notebooks_unpacked
        ]

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
