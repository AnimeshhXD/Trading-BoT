"""
test_validators.py — Unit tests for bot.validators.

Tests are grouped by validator function.  Each test is intentionally small,
named to be self-documenting, and free of mocks — validators are pure
functions with no side effects.

Run with:
    pytest tests/test_validators.py -v
"""

from __future__ import annotations

import pytest

from bot.exceptions import InvalidParameterError, MissingParameterError
from bot.models import OrderRequest, OrderSide, OrderType
from bot.validators import (
    validate_order_request,
    validate_order_type,
    validate_price,
    validate_price_requirements,
    validate_quantity,
    validate_side,
    validate_symbol,
)


# ===========================================================================
# validate_symbol
# ===========================================================================


class TestValidateSymbol:
    def test_valid_symbol_passes(self) -> None:
        validate_symbol("BTCUSDT")  # should not raise

    def test_lowercase_symbol_passes(self) -> None:
        validate_symbol("ethusdt")  # normalisation happens at CLI level

    def test_empty_string_raises(self) -> None:
        with pytest.raises(InvalidParameterError) as exc_info:
            validate_symbol("")
        assert exc_info.value.parameter == "symbol"

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(InvalidParameterError):
            validate_symbol("   ")


# ===========================================================================
# validate_side
# ===========================================================================


class TestValidateSide:
    def test_buy_passes(self) -> None:
        validate_side("BUY")

    def test_sell_passes(self) -> None:
        validate_side("SELL")

    def test_invalid_side_raises(self) -> None:
        with pytest.raises(InvalidParameterError) as exc_info:
            validate_side("LONG")
        assert exc_info.value.parameter == "side"

    def test_lowercase_buy_passes(self) -> None:
        """validate_side normalises to uppercase internally."""
        validate_side("buy")

    def test_empty_raises(self) -> None:
        with pytest.raises(InvalidParameterError):
            validate_side("")


# ===========================================================================
# validate_order_type
# ===========================================================================


class TestValidateOrderType:
    def test_market_passes(self) -> None:
        validate_order_type("MARKET")

    def test_limit_passes(self) -> None:
        validate_order_type("LIMIT")

    def test_stop_limit_passes(self) -> None:
        validate_order_type("STOP_LIMIT")

    def test_invalid_type_raises(self) -> None:
        with pytest.raises(InvalidParameterError) as exc_info:
            validate_order_type("OCO")
        assert exc_info.value.parameter == "order_type"


# ===========================================================================
# validate_quantity
# ===========================================================================


class TestValidateQuantity:
    def test_positive_quantity_passes(self) -> None:
        validate_quantity(0.001)

    def test_zero_raises(self) -> None:
        with pytest.raises(InvalidParameterError) as exc_info:
            validate_quantity(0.0)
        assert exc_info.value.parameter == "quantity"

    def test_negative_raises(self) -> None:
        with pytest.raises(InvalidParameterError):
            validate_quantity(-1.5)

    def test_none_raises(self) -> None:
        with pytest.raises(InvalidParameterError):
            validate_quantity(None)

    def test_large_quantity_passes(self) -> None:
        validate_quantity(999_999.999)


# ===========================================================================
# validate_price
# ===========================================================================


class TestValidatePrice:
    def test_positive_price_passes(self) -> None:
        validate_price(108_000.0)

    def test_zero_raises(self) -> None:
        with pytest.raises(InvalidParameterError) as exc_info:
            validate_price(0.0)
        assert exc_info.value.parameter == "price"

    def test_negative_raises(self) -> None:
        with pytest.raises(InvalidParameterError):
            validate_price(-100.0)

    def test_custom_field_name_appears_in_error(self) -> None:
        with pytest.raises(InvalidParameterError) as exc_info:
            validate_price(0.0, field_name="stop_price")
        assert exc_info.value.parameter == "stop_price"


# ===========================================================================
# validate_price_requirements (cross-field)
# ===========================================================================


class TestValidatePriceRequirements:
    def test_market_ignores_price(self) -> None:
        """MARKET orders never need a price."""
        validate_price_requirements(OrderType.MARKET, price=None, stop_price=None)

    def test_limit_with_price_passes(self) -> None:
        validate_price_requirements(OrderType.LIMIT, price=108_000.0, stop_price=None)

    def test_limit_without_price_raises_missing(self) -> None:
        with pytest.raises(MissingParameterError) as exc_info:
            validate_price_requirements(OrderType.LIMIT, price=None, stop_price=None)
        assert exc_info.value.parameter == "price"

    def test_stop_limit_with_both_prices_passes(self) -> None:
        validate_price_requirements(
            OrderType.STOP_LIMIT, price=108_500.0, stop_price=108_000.0
        )

    def test_stop_limit_missing_price_raises(self) -> None:
        with pytest.raises(MissingParameterError) as exc_info:
            validate_price_requirements(
                OrderType.STOP_LIMIT, price=None, stop_price=108_000.0
            )
        assert exc_info.value.parameter == "price"

    def test_stop_limit_missing_stop_price_raises(self) -> None:
        with pytest.raises(MissingParameterError) as exc_info:
            validate_price_requirements(
                OrderType.STOP_LIMIT, price=108_500.0, stop_price=None
            )
        assert exc_info.value.parameter == "stop_price"

    def test_limit_with_zero_price_raises_invalid(self) -> None:
        with pytest.raises(InvalidParameterError):
            validate_price_requirements(OrderType.LIMIT, price=0.0, stop_price=None)


# ===========================================================================
# validate_order_request (composite)
# ===========================================================================


class TestValidateOrderRequest:
    def _make_market_request(self, **overrides) -> OrderRequest:
        defaults = dict(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=0.001,
        )
        defaults.update(overrides)
        return OrderRequest(**defaults)

    def _make_limit_request(self, **overrides) -> OrderRequest:
        defaults = dict(
            symbol="BTCUSDT",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=0.001,
            price=108_000.0,
        )
        defaults.update(overrides)
        return OrderRequest(**defaults)

    def _make_stop_limit_request(self, **overrides) -> OrderRequest:
        defaults = dict(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.STOP_LIMIT,
            quantity=0.001,
            price=108_500.0,
            stop_price=108_000.0,
        )
        defaults.update(overrides)
        return OrderRequest(**defaults)

    def test_valid_market_order_passes(self) -> None:
        validate_order_request(self._make_market_request())

    def test_valid_limit_order_passes(self) -> None:
        validate_order_request(self._make_limit_request())

    def test_valid_stop_limit_order_passes(self) -> None:
        validate_order_request(self._make_stop_limit_request())

    def test_market_order_with_zero_quantity_raises(self) -> None:
        with pytest.raises(InvalidParameterError):
            validate_order_request(self._make_market_request(quantity=0.0))

    def test_limit_order_without_price_raises(self) -> None:
        with pytest.raises(MissingParameterError):
            validate_order_request(self._make_limit_request(price=None))

    def test_stop_limit_without_stop_price_raises(self) -> None:
        with pytest.raises(MissingParameterError):
            validate_order_request(self._make_stop_limit_request(stop_price=None))

    def test_empty_symbol_raises(self) -> None:
        with pytest.raises(InvalidParameterError):
            validate_order_request(self._make_market_request(symbol=""))
