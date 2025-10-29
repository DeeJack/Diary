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
        notebook_unpacked = msgpack.unpackb(uncompressed_notebook, raw=False)
        logging.getLogger("NotebookDAO").debug("Decryption completed successfully!")
        return Notebook.from_dict(notebook_unpacked)  # pyright: ignore[reportUnknownArgumentType]

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
