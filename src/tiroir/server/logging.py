"""Server logging (ADR-002): JSON lines on stdout, standard loggers included."""

import logging
import sys
from typing import override

from loguru import logger


class InterceptHandler(logging.Handler):
    """Route standard library records (Uvicorn, MCP SDK, httpx) into loguru."""

    @override
    def emit(self, record: logging.LogRecord) -> None:
        level: str | int
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        # Depth 6 skips the logging module's own frames to reach the caller.
        logger.opt(depth=6, exception=record.exc_info).log(level, record.getMessage())


def configure_logging(level: str = "INFO") -> None:
    """Send every log to stdout as JSON lines; tracebacks show no variables."""
    logger.remove()
    logger.add(sys.stdout, level=level, serialize=True, diagnose=False)
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
