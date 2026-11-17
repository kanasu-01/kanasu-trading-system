"""Small staging safety boundary shared by API, broker and runtime code."""

import importlib
import logging
import os


def staging_enabled() -> bool:
    value = os.getenv("KANASU_STAGING_MODE")
    if value is not None and value.strip().lower() not in {"true", "false", "1", "0"}:
        raise RuntimeError("Invalid staging mode configuration")
    if "RENDER" in os.environ or "KANASU_STAGING_PASSWORD_VERIFIER" in os.environ:
        return True
    return value is not None and value.strip().lower() in {"true", "1"}


def safe_failure(exc: Exception, message: str) -> Exception:
    return RuntimeError(message) if staging_enabled() else exc


def log_failure(logger: logging.Logger, message: str) -> None:
    if staging_enabled():
        logger.error(message)
    else:
        logger.exception(message)


def disable_smartapi_logging() -> None:
    """Fail closed if pinned SmartAPI logger structure changes."""
    from SmartApi import SmartConnect

    http = importlib.import_module(SmartConnect.__module__)
    ws = importlib.import_module("SmartApi.smartWebSocketV2")
    websocket_logging = importlib.import_module("websocket._logging")
    websocket_logger = getattr(websocket_logging, "_logger", None)
    if (
        not isinstance(websocket_logger, logging.Logger)
        or websocket_logger.name != "websocket"
    ):
        raise RuntimeError("websocket-client logging structure changed; staging blocked")
    targets = [
        getattr(http, "logger", None),
        getattr(http, "log", None),
        getattr(ws, "logger", None),
        websocket_logger,
    ]
    for target in targets:
        if target is not None and not isinstance(target, logging.Logger):
            raise RuntimeError("SmartAPI logging structure changed; staging blocked")
    if not isinstance(targets[0], logging.Logger) or not isinstance(targets[2], logging.Logger):
        raise RuntimeError("SmartAPI logging structure changed; staging blocked")
    for target in targets:
        if target is not None:
            target.disabled = True
            target.propagate = False
