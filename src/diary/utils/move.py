import logging
import os
import shutil
import tempfile
from pathlib import Path


def atomic_copy(input_file: Path, output_file: Path):
    """Copy a file atomically (creating a copy and moving using rename)"""
    output_dir = output_file.parent
    with tempfile.NamedTemporaryFile(suffix=".bac", dir=output_dir, delete=False) as f:
        filename = f.name
        logging.getLogger("Move").debug(
            "Writing backup from %s to %s", input_file, output_file
        )
        try:
            _ = shutil.copy2(input_file, filename)
        except Exception as e:
            logging.getLogger("Move").error("Error during backup: %s", e)
            os.remove(filename)
            return
    os.rename(filename, output_file)
