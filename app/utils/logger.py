# utils/logger.py
import logging

def get_logger(name: str = "cipher_pol"):
    logger = logging.getLogger(name)
    if not logger.handlers:
        # Prevents adding multiple handlers during auto-reload
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "[%(levelname)s] %(asctime)s %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger

# For convenience, provide a module-level logger
logger = get_logger()