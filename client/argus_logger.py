import os
import logging
from logging.handlers import RotatingFileHandler

LOGGING_LEVEL = getattr(
    logging, os.getenv("PYTHON_LOGGING_LEVEL", "INFO").upper(), logging.WARNING
)

logger = logging.getLogger()
logger.setLevel(LOGGING_LEVEL)

stream_handler = logging.StreamHandler()
file_handler = RotatingFileHandler("argus.log", maxBytes=5 * 1024 * 1024, backupCount=3)

formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
stream_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)

logger.addHandler(stream_handler)
logger.addHandler(file_handler)
