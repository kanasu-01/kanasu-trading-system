from typing import Callable, Any
from core.logging.logger import get_logger

logger = get_logger(__name__)


def safe_execute(fn: Callable, *args, **kwargs) -> Any:
    """
    Execute a function safely.
    """

    try:
        return fn(*args, **kwargs)
    except Exception as e:
        logger.error(
            f"Critical failure in {fn.__name__}",
            extra={"error": str(e)},
        )
        return None
