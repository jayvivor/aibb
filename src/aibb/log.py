import logging
import os
from datetime import datetime

LOG_DIR = "logs"
LOG_FORMAT = "%(asctime)s %(levelname)-7s %(message)s"


def get_logger() -> logging.Logger:
    logger = logging.getLogger("aibb")
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter(LOG_FORMAT)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    os.makedirs(LOG_DIR, exist_ok=True)
    file_handler = logging.FileHandler(os.path.join(LOG_DIR, f"{datetime.now():%Y-%m-%d-%H%M%S}.log"))
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger