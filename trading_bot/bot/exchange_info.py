"""
exchange_info.py — Validates orders against real Binance trading rules.

Design
------
Binance imposes strict rules for each symbol (tick size, step size).
If we submit a quantity that doesn't align with the step size (e.g., 0.11 when
step size is 0.1), the exchange rejects it. To fail fast and save API calls,
we fetch the rules once and validate locally.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from bot.exceptions import InvalidParameterError, TradingBotError
from bot.models import OrderRequest


class ExchangeInfoService:
    """Caches exchange info and validates orders against trading rules."""

    def __init__(self) -> None:
        self._filters_cache: dict[str, dict[str, str]] = {}

    def load_from_api(self, raw_exchange_info: dict) -> None:
        """Parse and cache the raw exchange info dictionary.
        
        Parameters
        ----------
        raw_exchange_info:
            The raw dict returned by ``futures_exchange_info()``.
        """
        for symbol_info in raw_exchange_info.get("symbols", []):
            symbol = symbol_info["symbol"]
            filters = {f["filterType"]: f for f in symbol_info.get("filters", [])}
            
            # Extract only what we need: PRICE_FILTER and LOT_SIZE
            price_filter = filters.get("PRICE_FILTER", {})
            lot_size = filters.get("LOT_SIZE", {})
            min_notional = filters.get("MIN_NOTIONAL", {})
            
            self._filters_cache[symbol] = {
                "tickSize": price_filter.get("tickSize", "0"),
                "stepSize": lot_size.get("stepSize", "0"),
                "minQty": lot_size.get("minQty", "0"),
                "minNotional": min_notional.get("notional", "0"),
            }

    def validate_order(self, request: OrderRequest) -> None:
        """Validate an order request against cached exchange rules.
        
        Raises
        ------
        TradingBotError
            If the symbol is unknown (cache miss).
        InvalidParameterError
            If the order violates step size, tick size, or min quantity.
        """
        rules = self._filters_cache.get(request.symbol)
        if not rules:
            raise TradingBotError(
                f"Symbol {request.symbol} not found in exchange info. "
                "Check symbol spelling or exchange availability."
            )
            
        tick_size = Decimal(rules["tickSize"])
        step_size = Decimal(rules["stepSize"])
        min_qty = Decimal(rules["minQty"])
        min_notional = Decimal(rules["minNotional"])
        
        # 1. Validate Quantity against minQty and stepSize
        if step_size > 0:
            if request.quantity < min_qty:
                raise InvalidParameterError(
                    "quantity",
                    f"must be >= minQty ({min_qty}) for {request.symbol}"
                )
            
            # (quantity - minQty) % stepSize == 0 (with Decimal precision)
            remainder = (request.quantity - min_qty) % step_size
            if remainder != Decimal("0"):
                raise InvalidParameterError(
                    "quantity",
                    f"must be a multiple of stepSize ({step_size}) "
                    f"starting from minQty ({min_qty})"
                )

        # 2. Validate limit price against tickSize
        if request.price is not None and tick_size > 0:
            if request.price % tick_size != Decimal("0"):
                raise InvalidParameterError(
                    "price",
                    f"must be a multiple of tickSize ({tick_size}) for {request.symbol}"
                )

        # 3. Validate stop price against tickSize
        if request.stop_price is not None and tick_size > 0:
            if request.stop_price % tick_size != Decimal("0"):
                raise InvalidParameterError(
                    "stop_price",
                    f"must be a multiple of tickSize ({tick_size}) for {request.symbol}"
                )

        # 4. Validate min notional (if price is known)
        if min_notional > 0 and request.price is not None:
            notional = request.quantity * request.price
            if notional < min_notional:
                raise InvalidParameterError(
                    "quantity/price",
                    f"Notional value ({notional}) is less than minNotional ({min_notional})"
                )
