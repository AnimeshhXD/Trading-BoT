"""
constants.py — Application-wide literals and defaults.

Design
------
Every magic string, numeric default, and endpoint URL is defined here with
a ``Final`` type annotation.  No other module may hardcode these values.

Using ``Final`` (PEP 591) instead of plain assignments signals to type
checkers (mypy / pyright) that these bindings must not be reassigned, giving
us a lightweight equivalent of true compile-time constants.
"""

from typing import Final

# ---------------------------------------------------------------------------
# Binance Futures API
# ---------------------------------------------------------------------------

TESTNET_BASE_URL: Final[str] = "https://testnet.binancefuture.com"
PROD_BASE_URL: Final[str] = "https://fapi.binance.com"

# ---------------------------------------------------------------------------
# Request Defaults
# ---------------------------------------------------------------------------

#: Maximum age (in milliseconds) of a request relative to server time.
#: Binance rejects requests outside this window to prevent replay attacks.
DEFAULT_RECV_WINDOW: Final[int] = 5_000

#: Seconds to wait for a response before raising TimeoutError.
DEFAULT_REQUEST_TIMEOUT: Final[int] = 10

from decimal import Decimal

# ---------------------------------------------------------------------------
# Order Constraints
# ---------------------------------------------------------------------------

#: Minimum positive value accepted for price / quantity / stopPrice fields.
MIN_POSITIVE_VALUE: Final[Decimal] = Decimal("0")

# ---------------------------------------------------------------------------
# Supported Order Configuration
# ---------------------------------------------------------------------------

#: Raw string values that Binance accepts for order sides.
SUPPORTED_SIDES: Final[tuple[str, ...]] = ("BUY", "SELL")

#: Raw string values that Binance accepts for order types on Futures.
SUPPORTED_ORDER_TYPES: Final[tuple[str, ...]] = (
    "MARKET",
    "LIMIT",
    "STOP",          # Binance Futures STOP == stop-limit
)

#: Time-in-force values used by LIMIT and STOP orders.
TIME_IN_FORCE_GTC: Final[str] = "GTC"   # Good Till Cancelled
TIME_IN_FORCE_IOC: Final[str] = "IOC"   # Immediate Or Cancel
TIME_IN_FORCE_FOK: Final[str] = "FOK"   # Fill Or Kill

DEFAULT_TIME_IN_FORCE: Final[str] = TIME_IN_FORCE_GTC

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_DIR: Final[str] = "logs"
LOG_FILE: Final[str] = "logs/trading.log"

#: Rotate the log file once it reaches this size.
LOG_ROTATION_SIZE: Final[str] = "5 MB"

#: Keep at most this many rotated log files.
LOG_RETENTION: Final[str] = "10 days"

#: Loguru format for the rotating file sink — includes full context.
LOG_FILE_FORMAT: Final[str] = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
    "{name}:{function}:{line} | {message}"
)

#: Loguru format for the console sink — concise, human-readable.
LOG_CONSOLE_FORMAT: Final[str] = (
    "<green>{time:HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan> | "
    "{message}"
)

# ---------------------------------------------------------------------------
# CLI Display
# ---------------------------------------------------------------------------

DIVIDER_WIDE: Final[str] = "=" * 50
DIVIDER_NARROW: Final[str] = "-" * 50

APP_BANNER: Final[str] = "BINANCE FUTURES TESTNET"
