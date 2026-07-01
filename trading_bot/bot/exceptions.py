"""
exceptions.py — Domain-specific exception hierarchy.

Design
------
Every recoverable error condition in the application maps to a dedicated
exception class.  All exceptions share a single root (TradingBotError) so
callers can choose between fine-grained or broad catching.

Hierarchy
---------
TradingBotError
├── ValidationError
│   ├── MissingParameterError
│   └── InvalidParameterError
├── ExchangeError
│   ├── BinanceApiError
│   ├── BinanceRequestError
│   └── AuthenticationError
└── NetworkError
    └── TimeoutError
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Root
# ---------------------------------------------------------------------------


class TradingBotError(Exception):
    """Base class for all application-level exceptions.

    Parameters
    ----------
    message:
        Human-readable description of the error shown in the CLI and logs.
    """

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)

    def __str__(self) -> str:  # pragma: no cover
        return self.message


# ---------------------------------------------------------------------------
# Validation Errors
# ---------------------------------------------------------------------------


class ValidationError(TradingBotError):
    """Raised when user-supplied input fails business-rule validation."""


class MissingParameterError(ValidationError):
    """Raised when a required CLI parameter is absent for a given order type.

    Example
    -------
    LIMIT orders require ``--price``; if omitted, this exception is raised.
    """

    def __init__(self, parameter: str, order_type: str) -> None:
        self.parameter = parameter
        self.order_type = order_type
        super().__init__(
            f"Parameter '{parameter}' is required for {order_type} orders."
        )


class InvalidParameterError(ValidationError):
    """Raised when a parameter is present but its value is out of range or
    otherwise invalid.

    Example
    -------
    ``quantity=-0.5`` violates the rule that quantity must be positive.
    """

    def __init__(self, parameter: str, reason: str) -> None:
        self.parameter = parameter
        self.reason = reason
        super().__init__(f"Invalid value for '{parameter}': {reason}")


# ---------------------------------------------------------------------------
# Exchange / API Errors
# ---------------------------------------------------------------------------


class ExchangeError(TradingBotError):
    """Raised when the Binance API returns an error response."""


class BinanceApiError(ExchangeError):
    """Wraps a python-binance BinanceAPIException.

    Carries the original Binance error code for structured logging.
    """

    def __init__(self, code: int, message: str) -> None:
        self.code = code
        super().__init__(f"Binance API error {code}: {message}")


class BinanceRequestError(ExchangeError):
    """Wraps a python-binance BinanceRequestException (malformed requests)."""


class AuthenticationError(ExchangeError):
    """Raised when API key / secret validation fails (HTTP 401/403)."""

    def __init__(self, message: str | None = None) -> None:
        if message is None:
            message = (
                "Authentication failed. Verify BINANCE_API_KEY and "
                "BINANCE_API_SECRET in your .env file."
            )
        super().__init__(message)



# ---------------------------------------------------------------------------
# Network Errors
# ---------------------------------------------------------------------------


class NetworkError(TradingBotError):
    """Raised for connectivity problems unrelated to Binance API logic."""


class TimeoutError(NetworkError):
    """Raised when a request to Binance exceeds the configured timeout."""

    def __init__(self) -> None:
        super().__init__(
            "Request timed out. Check your internet connection and try again."
        )
