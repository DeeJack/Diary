import datetime
import logging
from typing import override


from diary.config import settings


def configure_logging():
    now: str = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M")
    FILE_NAME = settings.LOGGING_DIR_PATH / f"{now}.log"

    formatter = logging.Formatter(
        fmt="%(asctime)s - [%(name)s]- %(levelname)s - [%(module)s:%(levelno)s] - %(message)s"
    )

    file_handler = logging.FileHandler(FILE_NAME, encoding="UTF-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(CustomFormatter())

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    modules_to_ignore: list[str] = []
    for module in modules_to_ignore:
        logging.getLogger(module).setLevel(logging.WARNING)


class CustomFormatter(logging.Formatter):
    grey: str = "\x1b[38;20m"
    yellow: str = "\x1b[33;20m"
    red: str = "\x1b[31;20m"
    bold_red: str = "\x1b[31;1m"
    reset: str = "\x1b[0m"
    custom_format: str = (
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"
    )

    FORMATS = {
        logging.DEBUG: grey + custom_format + reset,
        logging.INFO: grey + custom_format + reset,
        logging.WARNING: yellow + custom_format + reset,
        logging.ERROR: red + custom_format + reset,
        logging.CRITICAL: bold_red + custom_format + reset,
    }

    @override
    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)
