"""
models.py — Enums and dataclasses for the trading bot domain.

Design
------
This module defines the *language* of the system.  Every layer speaks in
terms of these types rather than raw strings or dicts:

  CLI  →  OrderRequest  →  OrderService  →  BinanceClient  →  OrderResponse  →  CLI

Enums
-----
``OrderSide``   : BUY or SELL.
``OrderType``   : MARKET, LIMIT, or STOP_LIMIT.
``OrderStatus`` : The lifecycle state returned by Binance.

Dataclasses
-----------
``OrderRequest``  : Validated, typed payload built by the CLI.
``OrderResponse`` : Parsed, typed view of Binance's JSON response.

Note on ``str, Enum`` mixin
---------------------------
Inheriting from both ``str`` and ``Enum`` means the enum member *is* a
string.  python-binance accepts these directly without calling ``.value``,
which keeps call sites clean.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class OrderSide(str, Enum):
    """Direction of a futures order."""

    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    """Supported order execution types.

    Binance Futures uses ``STOP`` for what traders call *stop-limit* orders.
    The CLI exposes this as ``STOP_LIMIT`` for clarity and maps it internally.
    """

    MARKET = "MARKET"
    LIMIT = "LIMIT"
    #: Exposed to the user as STOP_LIMIT; maps to Binance's "STOP" type.
    STOP_LIMIT = "STOP"


class OrderStatus(str, Enum):
    """Lifecycle states an order can be in, as returned by Binance."""

    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    EXPIRED_IN_MATCH = "EXPIRED_IN_MATCH"


# ---------------------------------------------------------------------------
# Request Model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OrderRequest:
    """Immutable, validated payload representing a single order intent.

    Instances are created by the CLI after validation and passed directly to
    ``OrderService``.  ``frozen=True`` prevents accidental mutation between
    layers.

    Parameters
    ----------
    symbol:
        Trading pair in Binance notation, e.g. ``"BTCUSDT"``.
    side:
        Direction of the order — BUY or SELL.
    order_type:
        Execution type — MARKET, LIMIT, or STOP_LIMIT.
    quantity:
        Contract quantity to trade.  Must be > 0.
    price:
        Limit price.  Required for LIMIT and STOP_LIMIT; ``None`` for MARKET.
    stop_price:
        Trigger price.  Required for STOP_LIMIT; ``None`` otherwise.
    time_in_force:
        Order duration policy.  Defaults to GTC (Good Till Cancelled).
        Injected by the service layer for LIMIT / STOP_LIMIT orders.
    """

    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    price: Optional[Decimal] = field(default=None)
    stop_price: Optional[Decimal] = field(default=None)
    time_in_force: Optional[str] = field(default=None)

    def requires_price(self) -> bool:
        """Return ``True`` if this order type mandates a limit price."""
        return self.order_type in (OrderType.LIMIT, OrderType.STOP_LIMIT)

    def requires_stop_price(self) -> bool:
        """Return ``True`` if this order type mandates a stop trigger price."""
        return self.order_type == OrderType.STOP_LIMIT

    def is_market(self) -> bool:
        """Return ``True`` for MARKET orders (price fields are ignored)."""
        return self.order_type == OrderType.MARKET


# ---------------------------------------------------------------------------
# Response Model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OrderResponse:
    """Parsed, typed representation of a Binance order placement response.

    Constructed by ``BinanceClient`` from the raw API dict so that no other
    layer needs to know Binance's key names or type coercions.

    Parameters
    ----------
    order_id:
        Unique integer ID assigned by Binance.
    symbol:
        The trading pair the order was placed on.
    side:
        BUY or SELL, re-parsed as ``OrderSide``.
    order_type:
        Execution type, re-parsed as ``OrderType``.
    status:
        Current lifecycle status, parsed as ``OrderStatus``.
    quantity:
        Originally requested quantity (``origQty``).
    executed_qty:
        Quantity actually filled so far (``executedQty``).
    avg_price:
        Volume-weighted average fill price (``avgPrice``).  Zero for unfilled
        orders.
    raw:
        The original response dict retained for debugging / extension.
    """

    order_id: int
    symbol: str
    side: OrderSide
    order_type: OrderType
    status: OrderStatus
    quantity: Decimal
    executed_qty: Decimal
    avg_price: Decimal
    raw: dict = field(default_factory=dict, compare=False, repr=False)

    @classmethod
    def from_api_response(cls, data: dict) -> "OrderResponse":
        """Construct an ``OrderResponse`` from a raw Binance API response dict."""

        print("\n========== PARSER INPUT ==========")
        print(data)
        print("==================================\n")

        try:
            available_keys = list(data.keys())
        except Exception:
            available_keys = []

        print("Available Keys:", available_keys)

        required_keys = [
            "orderId",
            "symbol",
            "side",
            "type",
            "status",
            "origQty",
            "executedQty",
        ]
        missing_keys = [k for k in required_keys if k not in data]

        if missing_keys:
            print("Missing Keys:", missing_keys)
            raise ValueError(
                f"Binance response missing required keys: {missing_keys}. "
                f"Available keys: {available_keys}"
            )

        print("Reading orderId...")
        order_id_raw = data["orderId"]

        print("Reading symbol...")
        symbol_raw = data["symbol"]

        print("Reading side...")
        side_raw = data["side"]

        print("Reading type...")
        type_raw = data["type"]

        print("Reading status...")
        status_raw = data["status"]

        print("Reading origQty...")
        orig_qty_raw = data["origQty"]

        print("Reading executedQty...")
        executed_qty_raw = data["executedQty"]

        print("Reading avgPrice...")
        avg_price_raw = data.get("avgPrice", "0")

        return cls(
            order_id=int(order_id_raw),
            symbol=str(symbol_raw),
            side=OrderSide(side_raw),
            order_type=OrderType(type_raw),
            status=OrderStatus(status_raw),

            quantity=Decimal(str(orig_qty_raw)),
            executed_qty=Decimal(str(executed_qty_raw)),
            avg_price=Decimal(str(avg_price_raw)),
            raw=data,
        )

