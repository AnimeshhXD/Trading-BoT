"""
test_orders.py — Unit tests for OrderService.

All Binance network calls are replaced with ``unittest.mock`` fakes so
tests run offline without any credentials.

Patterns used
-------------
- ``MagicMock`` — replaces ``BinanceClient`` to intercept dispatch calls.
- ``patch`` — used for ``validate_order_request`` in isolation tests.
- Fixture factories produce ready-to-use ``OrderRequest`` objects so each
  test stays focused on one behaviour.

Run with:
    pytest tests/test_orders.py -v
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from bot.exceptions import BinanceApiError, ValidationError
from bot.models import OrderRequest, OrderResponse, OrderSide, OrderStatus, OrderType
from bot.orders import OrderService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_mock_client() -> MagicMock:
    """Return a mock that behaves like a connected ``BinanceClient``."""
    client = MagicMock(spec=[
        "place_market_order", 
        "place_limit_order", 
        "place_stop_limit_order",
        "get_exchange_info"
    ])
    client.get_exchange_info.return_value = {
        "symbols": [
            {
                "symbol": "BTCUSDT",
                "filters": [
                    {"filterType": "PRICE_FILTER", "tickSize": "0.10"},
                    {"filterType": "LOT_SIZE", "stepSize": "0.001", "minQty": "0.001"},
                    {"filterType": "MIN_NOTIONAL", "notional": "5.0"}
                ]
            }
        ]
    }
    return client


def _make_mock_response(
    order_id: int = 12345678,
    status: OrderStatus = OrderStatus.NEW,
) -> OrderResponse:
    """Build a minimal ``OrderResponse`` for assertion purposes."""
    return OrderResponse(
        order_id=order_id,
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        status=status,
        quantity=Decimal("0.001"),
        executed_qty=Decimal("0"),
        avg_price=Decimal("0"),
    )


def _market_request() -> OrderRequest:
    return OrderRequest(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.001"),
    )


def _limit_request() -> OrderRequest:
    return OrderRequest(
        symbol="BTCUSDT",
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=Decimal("0.001"),
        price=Decimal("108000.0"),
    )


def _stop_limit_request() -> OrderRequest:
    return OrderRequest(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.STOP_LIMIT,
        quantity=Decimal("0.001"),
        price=Decimal("108500.0"),
        stop_price=Decimal("108000.0"),
    )


# ---------------------------------------------------------------------------
# Test: correct client method is called for each order type
# ---------------------------------------------------------------------------


class TestOrderServiceDispatch:
    def test_market_order_calls_place_market_order(self) -> None:
        mock_client = _make_mock_client()
        mock_response = _make_mock_response()
        mock_client.place_market_order.return_value = mock_response

        service = OrderService(mock_client)
        result = service.place_order(_market_request())

        mock_client.place_market_order.assert_called_once()
        mock_client.place_limit_order.assert_not_called()
        mock_client.place_stop_limit_order.assert_not_called()
        assert result.order_id == 12345678

    def test_limit_order_calls_place_limit_order(self) -> None:
        mock_client = _make_mock_client()
        mock_response = _make_mock_response()
        mock_client.place_limit_order.return_value = mock_response

        service = OrderService(mock_client)
        service.place_order(_limit_request())

        mock_client.place_limit_order.assert_called_once()
        mock_client.place_market_order.assert_not_called()

    def test_stop_limit_order_calls_place_stop_limit_order(self) -> None:
        mock_client = _make_mock_client()
        mock_response = _make_mock_response()
        mock_client.place_stop_limit_order.return_value = mock_response

        service = OrderService(mock_client)
        service.place_order(_stop_limit_request())

        mock_client.place_stop_limit_order.assert_called_once()


# ---------------------------------------------------------------------------
# Test: time_in_force injection
# ---------------------------------------------------------------------------


class TestTimeInForceInjection:
    def test_limit_order_gets_gtc_if_not_set(self) -> None:
        """OrderService must inject GTC for LIMIT when TIF is absent."""
        mock_client = _make_mock_client()
        mock_response = _make_mock_response()
        mock_client.place_limit_order.return_value = mock_response

        service = OrderService(mock_client)
        service.place_order(_limit_request())

        # Inspect the OrderRequest that was passed to the client
        call_args = mock_client.place_limit_order.call_args
        sent_request: OrderRequest = call_args[0][0]
        assert sent_request.time_in_force == "GTC"

    def test_market_order_does_not_inject_tif(self) -> None:
        mock_client = _make_mock_client()
        mock_response = _make_mock_response()
        mock_client.place_market_order.return_value = mock_response

        service = OrderService(mock_client)
        service.place_order(_market_request())

        call_args = mock_client.place_market_order.call_args
        sent_request: OrderRequest = call_args[0][0]
        assert sent_request.time_in_force is None

    def test_explicit_tif_is_preserved(self) -> None:
        """User-supplied TIF must not be overwritten."""
        mock_client = _make_mock_client()
        mock_response = _make_mock_response()
        mock_client.place_limit_order.return_value = mock_response

        request = replace(_limit_request(), time_in_force="FOK")
        service = OrderService(mock_client)
        service.place_order(request)

        call_args = mock_client.place_limit_order.call_args
        sent_request: OrderRequest = call_args[0][0]
        assert sent_request.time_in_force == "FOK"


# ---------------------------------------------------------------------------
# Test: validation errors surface correctly
# ---------------------------------------------------------------------------


class TestOrderServiceValidation:
    def test_invalid_quantity_raises_before_calling_client(self) -> None:
        mock_client = _make_mock_client()
        service = OrderService(mock_client)

        bad_request = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("-1.0"),  # invalid
        )

        with pytest.raises(ValidationError):
            service.place_order(bad_request)

        mock_client.place_market_order.assert_not_called()

    def test_missing_price_raises_before_calling_client(self) -> None:
        mock_client = _make_mock_client()
        service = OrderService(mock_client)

        bad_request = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("0.001"),
            price=None,  # missing for LIMIT
        )

        with pytest.raises(ValidationError):
            service.place_order(bad_request)

        mock_client.place_limit_order.assert_not_called()


# ---------------------------------------------------------------------------
# Test: API errors propagate correctly
# ---------------------------------------------------------------------------


class TestOrderServiceErrorPropagation:
    def test_binance_api_error_propagates(self) -> None:
        mock_client = _make_mock_client()
        mock_client.place_market_order.side_effect = BinanceApiError(
            code=-2010, message="Insufficient balance."
        )

        service = OrderService(mock_client)

        with pytest.raises(BinanceApiError) as exc_info:
            service.place_order(_market_request())

        assert exc_info.value.code == -2010

    def test_response_order_id_is_returned(self) -> None:
        mock_client = _make_mock_client()
        mock_client.place_market_order.return_value = _make_mock_response(order_id=99887766)

        service = OrderService(mock_client)
        result = service.place_order(_market_request())

        assert result.order_id == 99887766

    def test_response_status_is_returned(self) -> None:
        mock_client = _make_mock_client()
        mock_client.place_market_order.return_value = _make_mock_response(
            status=OrderStatus.FILLED
        )

        service = OrderService(mock_client)
        result = service.place_order(_market_request())

        assert result.status == OrderStatus.FILLED
