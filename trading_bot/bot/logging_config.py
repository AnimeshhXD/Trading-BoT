"""
logging_config.py — Loguru logger configuration.

Design
------
Two sinks are registered on the shared Loguru ``logger`` instance:

1. **Console sink** — INFO level and above, concise format, coloured output.
   Meant for the operator watching the terminal.

2. **File sink** — DEBUG level and above, detailed format, auto-rotated at
   5 MB, retained for 10 days, serialised as plain text.
   Meant for post-incident analysis or audit trails.

Usage
-----
Import the pre-configured logger in any module::

    from bot.logging_config import get_logger

    log = get_logger(__name__)
    log.info("Order submitted", order_id=12345)

The ``get_logger`` wrapper binds a ``name`` context so log entries in the
file include the originating module path.

Idempotency
-----------
``setup_logging()`` is guarded by a module-level flag so calling it multiple
times (e.g. during tests) does not register duplicate sinks.
"""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

from bot.constants import (
    LOG_CONSOLE_FORMAT,
    LOG_DIR,
    LOG_FILE,
    LOG_FILE_FORMAT,
    LOG_RETENTION,
    LOG_ROTATION_SIZE,
)

_logging_configured: bool = False


def setup_logging() -> None:
    """Configure console and file sinks on the Loguru root logger.

    Safe to call multiple times — subsequent calls are no-ops.
    """
    global _logging_configured

    if _logging_configured:
        return

    # Remove Loguru's default handler so we control every sink.
    logger.remove()



    # --- Console sink --------------------------------------------------------
    logger.add(
        sys.stderr,
        level="INFO",
        format=LOG_CONSOLE_FORMAT,
        colorize=True,
        backtrace=False,
        diagnose=False,
    )

    # --- File sink -----------------------------------------------------------
    Path(LOG_DIR).mkdir(parents=True, exist_ok=True)

    logger.add(
        LOG_FILE,
        level="DEBUG",
        format=LOG_FILE_FORMAT,
        rotation=LOG_ROTATION_SIZE,
        retention=LOG_RETENTION,
        compression="zip",
        encoding="utf-8",
        backtrace=True,
        diagnose=True,
        enqueue=True,
    )

    _logging_configured = True


def get_logger(name: str):  # type: ignore[return]
    """Return a Loguru logger bound with the given module name."""
    setup_logging()
    return logger.bind(name=name)

