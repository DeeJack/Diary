"""Legacy encrypted notebook loader (used only for migration)"""

import logging
from pathlib import Path
from typing import Callable, cast

import msgpack
import zstd

from diary.models.notebook import Notebook
from diary.models.page import Page
from diary.utils import encryption


def load_legacy_notebook(
    filepath: Path,
    key_buffer: encryption.SecureBuffer,
    progress: Callable[[int, int], None] | None = None,
) -> Notebook:
    """Load a legacy encrypted notebook using the derived key."""
    if not filepath.exists():
        logging.getLogger("LegacyLoader").debug(
            "Notebook does not exist, returning a new notebook"
        )
        return Notebook(pages=[Page()])

    logging.getLogger("LegacyLoader").debug("Loading legacy format")
    notebook_data = encryption.SecureEncryption.decrypt_file(
        filepath, key_buffer, progress
    )
    uncompressed_notebook = zstd.decompress(notebook_data)
    notebook_unpacked = cast(
        dict[str, str], msgpack.unpackb(uncompressed_notebook, raw=False)
    )
    notebook = Notebook.from_dict(notebook_unpacked)
    logging.getLogger("LegacyLoader").debug("Legacy decryption completed successfully")
    return notebook


def load_legacy_notebooks(
    filepath: Path,
    key_buffer: encryption.SecureBuffer,
    progress: Callable[[int, int], None] | None = None,
) -> list[Notebook]:
    """Load legacy encrypted notebooks using the derived key."""
    if not filepath.exists():
        logging.getLogger("LegacyLoader").debug(
            "Notebooks file does not exist, returning empty list"
        )
        return [Notebook([Page()])]  # Return one notebook with one page

    logging.getLogger("LegacyLoader").debug("Notebooks file exists, decrypting")
    notebooks_data = encryption.SecureEncryption.decrypt_file(
        filepath, key_buffer, progress
    )
    uncompressed_notebooks = zstd.decompress(notebooks_data)
    notebooks_unpacked = msgpack.unpackb(uncompressed_notebooks, raw=False)
    if isinstance(notebooks_unpacked, dict):
        logging.getLogger("LegacyLoader").debug(
            "Decryption completed successfully! 1 notebook found"
        )
        return [Notebook.from_dict(cast(dict[str, str], notebooks_unpacked))]

    notebook_dicts = cast(list[dict[str, str]], notebooks_unpacked)
    logging.getLogger("LegacyLoader").debug(
        "Decryption completed successfully! %s notebooks found",
        len(notebook_dicts),
    )
    return [Notebook.from_dict(notebook_dict) for notebook_dict in notebook_dicts]
