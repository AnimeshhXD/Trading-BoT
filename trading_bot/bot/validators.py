"""
validators.py — Stateless, reusable input validation functions.

Design
------
All validation logic is expressed as pure functions that raise typed
exceptions on failure and return ``None`` on success.  This keeps them
completely decoupled from Typer, Click, or any CLI framework.

Functions are intentionally small and single-purpose (SRP) so they can be
composed by ``validate_order_request`` for full order validation, and tested
individually.

The CLI calls ``validate_order_request`` once; individual validators are
exposed for unit tests and future reuse (e.g. a REST API layer).

Raises
------
InvalidParameterError
    When a field is present but its value violates a business rule.
MissingParameterError
    When a field required by the chosen order type is absent.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from bot.constants import MIN_POSITIVE_VALUE, SUPPORTED_ORDER_TYPES, SUPPORTED_SIDES
from bot.exceptions import InvalidParameterError, MissingParameterError
from bot.models import OrderRequest, OrderSide, OrderStatus, OrderType


# ---------------------------------------------------------------------------
# Primitive validators
# ---------------------------------------------------------------------------


def validate_symbol(symbol: str) -> None:
    """Ensure the trading symbol is a non-empty uppercase string.

    Parameters
    ----------
    symbol:
        Trading pair string supplied by the user, e.g. ``"btcusdt"``.

    Raises
    ------
    InvalidParameterError
        If the symbol is blank after stripping whitespace.
    """
    if not symbol or not symbol.strip():
        raise InvalidParameterError("symbol", "must be a non-empty string (e.g. BTCUSDT)")


def validate_side(side: str) -> None:
    """Ensure the order side is one of the supported values.

    Parameters
    ----------
    side:
        Raw side string from the CLI, e.g. ``"BUY"`` or ``"SELL"``.

    Raises
    ------
    InvalidParameterError
        If ``side`` is not ``"BUY"`` or ``"SELL"``.
    """
    if side.upper() not in SUPPORTED_SIDES:
        raise InvalidParameterError(
            "side",
            f"must be one of {SUPPORTED_SIDES}, got '{side}'",
        )


def validate_order_type(order_type: str) -> None:
    """Ensure the order type is supported by this application.

    Parameters
    ----------
    order_type:
        Raw order type string from the CLI.

    Raises
    ------
    InvalidParameterError
        If ``order_type`` is not in the supported set.
    """
    # Map the user-facing STOP_LIMIT to Binance's STOP for comparison.
    binance_type = "STOP" if order_type.upper() == "STOP_LIMIT" else order_type.upper()

    if binance_type not in SUPPORTED_ORDER_TYPES:
        raise InvalidParameterError(
            "order_type",
            f"must be one of MARKET, LIMIT, STOP_LIMIT, got '{order_type}'",
        )


def validate_quantity(quantity: Optional[Decimal]) -> None:
    """Ensure the order quantity is a positive number.

    Parameters
    ----------
    quantity:
        Number of contracts to trade.

    Raises
    ------
    InvalidParameterError
        If ``quantity`` is ``None``, zero, or negative.
    """
    if quantity is None or quantity <= MIN_POSITIVE_VALUE:
        raise InvalidParameterError(
            "quantity",
            f"must be a positive number greater than {MIN_POSITIVE_VALUE}, got '{quantity}'",
        )


def validate_price(price: Optional[Decimal], field_name: str = "price") -> None:
    """Ensure a price field is a positive number.

    Reused for both ``price`` and ``stopPrice`` fields.

    Parameters
    ----------
    price:
        The price value to validate.
    field_name:
        The parameter name to include in the error message (``"price"`` or
        ``"stop_price"``).

    Raises
    ------
    InvalidParameterError
        If the price is zero or negative.
    """
    if price is None or price <= MIN_POSITIVE_VALUE:
        raise InvalidParameterError(
            field_name,
            f"must be a positive number greater than {MIN_POSITIVE_VALUE}, got '{price}'",
        )


# ---------------------------------------------------------------------------
# Cross-field validators (order-type-aware)
# ---------------------------------------------------------------------------


def validate_price_requirements(
    order_type: OrderType,
    price: Optional[Decimal],
    stop_price: Optional[Decimal],
) -> None:
    """Enforce price-field rules that depend on the chosen order type.

    Rules
    -----
    - MARKET  : price and stop_price are ignored (no validation needed).
    - LIMIT   : price must be provided and positive.
    - STOP_LIMIT : price and stop_price must both be provided and positive.

    Parameters
    ----------
    order_type:
        The validated ``OrderType`` enum member.
    price:
        Limit price from the CLI.
    stop_price:
        Stop trigger price from the CLI.

    Raises
    ------
    MissingParameterError
        If a required price field is absent for the order type.
    InvalidParameterError
        If a required price field is present but not positive.
    """
    if order_type == OrderType.MARKET:
        return  # MARKET orders ignore price fields entirely

    if order_type in (OrderType.LIMIT, OrderType.STOP_LIMIT):
        if price is None:
            raise MissingParameterError("price", order_type.name)
        validate_price(price, "price")

    if order_type == OrderType.STOP_LIMIT:
        if stop_price is None:
            raise MissingParameterError("stop_price", order_type.name)
        validate_price(stop_price, "stop_price")


# ---------------------------------------------------------------------------
# Composite validator — single entry point for the CLI and tests
# ---------------------------------------------------------------------------


def validate_order_request(request: OrderRequest) -> None:
    """Run all validators against a fully constructed ``OrderRequest``.

    This is the single entry point called by ``OrderService`` before touching
    the Binance API.  Raises the first validation failure encountered.

    Parameters
    ----------
    request:
        The ``OrderRequest`` dataclass built by the CLI.

    Raises
    ------
    ValidationError
        Any subclass — ``InvalidParameterError`` or ``MissingParameterError``.
    """
    validate_symbol(request.symbol)
    validate_side(request.side.value)
    validate_order_type(request.order_type.name)
    validate_quantity(request.quantity)
    validate_price_requirements(
        order_type=request.order_type,
        price=request.price,
        stop_price=request.stop_price,
    )
