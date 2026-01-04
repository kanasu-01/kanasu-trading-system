import logging


def get_logger(name: str) -> logging.Logger:
    """
    Get a named logger for any module.
    """
    return logging.getLogger(name)
