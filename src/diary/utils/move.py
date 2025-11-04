"""Utils to copy a file safely, with copy to a temporary file and moving it with rename"""

import logging
import os
import shutil
import tempfile
from pathlib import Path


def atomic_copy(input_file: Path, output_file: Path):
    """Copy a file atomically (creating a copy and moving using rename)"""
    if not input_file.exists():
        logging.getLogger("Move").warning(
            "The input file (%s) doesn't exists, cannot copy to %s",
            input_file.as_posix(),
            output_file.as_posix(),
        )
        return
    output_dir = output_file.parent
    with tempfile.NamedTemporaryFile(suffix=".bac", dir=output_dir, delete=False) as f:
        filename = f.name
        logging.getLogger("Move").debug(
            "Writing backup from %s to %s", input_file, output_file
        )
        try:
            _ = shutil.copy2(input_file, filename)
            f.close()
            if output_file.exists():
                os.unlink(output_file)
            os.rename(filename, output_file)
        except (IOError, OSError) as e:
            logging.getLogger("Move").error("Error during backup: %s", e)
