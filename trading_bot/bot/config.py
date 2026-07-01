"""
config.py — Environment variable loading and application settings.

Design
------
A single ``Settings`` dataclass is populated once at import time from the
process environment (via python-dotenv).  Every other module imports
``settings`` from here — no module calls ``os.getenv`` directly.

This centralises all environment concerns in one place and makes the app
trivially testable: patch ``config.settings`` in a test to swap credentials
without touching the real environment.

Raises
------
``AuthenticationError``
    If either ``BINANCE_API_KEY`` or ``BINANCE_API_SECRET`` is absent from
    the environment after loading the ``.env`` file.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

from bot.constants import (
    DEFAULT_RECV_WINDOW,
    DEFAULT_REQUEST_TIMEOUT,
    PROD_BASE_URL,
    TESTNET_BASE_URL,
)
from bot.exceptions import AuthenticationError

# Load .env from the project root (two levels up from this file: bot/ → trading_bot/)
_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=_ENV_PATH)


@dataclass(frozen=True)
class Settings:
    """Immutable application configuration loaded from environment variables.

    Parameters
    ----------
    api_key:
        Binance API key.  Source: ``BINANCE_API_KEY`` env var.
    api_secret:
        Binance API secret.  Source: ``BINANCE_API_SECRET`` env var.
    use_testnet:
        Whether to connect to the Binance Futures Testnet or Production.
    testnet_url:
        Base URL for the Binance Futures Testnet REST API.
    prod_url:
        Base URL for the Binance Futures Production REST API.
    recv_window:
        Request validity window in milliseconds (anti-replay protection).
    request_timeout:
        Maximum seconds to wait for a Binance API response.
    """

    api_key: str
    api_secret: str
    use_testnet: bool = True
    testnet_url: str = field(default=TESTNET_BASE_URL)
    prod_url: str = field(default=PROD_BASE_URL)
    recv_window: int = field(default=DEFAULT_RECV_WINDOW)
    request_timeout: int = field(default=DEFAULT_REQUEST_TIMEOUT)

    @property
    def base_url(self) -> str:
        """Return the appropriate URL based on the environment."""
        return self.testnet_url if self.use_testnet else self.prod_url


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Read credentials from the environment and return a cached ``Settings`` object.

    Called lazily only when configuration is actually needed.

    Raises
    ------
    AuthenticationError
        If ``BINANCE_API_KEY`` or ``BINANCE_API_SECRET`` are missing or invalid.
    """
    api_key = os.getenv("BINANCE_API_KEY", "").strip()
    api_secret = os.getenv("BINANCE_API_SECRET", "").strip()

    if not api_key:
        raise AuthenticationError(
            "Missing environment variable: BINANCE_API_KEY\n\n"
            "Please create a .env file in the project root using .env.example."
        )

    if not api_secret:
        raise AuthenticationError(
            "Missing environment variable: BINANCE_API_SECRET\n\n"
            "Please create a .env file in the project root using .env.example."
        )

    use_testnet_str = os.getenv("USE_TESTNET", "true").strip().lower()
    if use_testnet_str in ("true", "1", "yes", "on"):
        use_testnet = True
    elif use_testnet_str in ("false", "0", "no", "off"):
        use_testnet = False
    else:
        raise AuthenticationError(
            f"Invalid environment variable value for USE_TESTNET: '{os.getenv('USE_TESTNET')}'\n\n"
            "Please set USE_TESTNET to 'true' or 'false' in your .env file."
        )

    return Settings(
        api_key=api_key, 
        api_secret=api_secret, 
        use_testnet=use_testnet
    )

