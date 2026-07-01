from __future__ import annotations

from decimal import Decimal
import pytest

from bot.exchange_info import ExchangeInfoService
from bot.exceptions import InvalidParameterError, TradingBotError
from bot.models import OrderRequest, OrderSide, OrderType


@pytest.fixture
def exchange_info_service() -> ExchangeInfoService:
    service = ExchangeInfoService()
    service.load_from_api({
        "symbols": [
            {
                "symbol": "BTCUSDT",
                "filters": [
                    {"filterType": "PRICE_FILTER", "tickSize": "0.10"},
                    {"filterType": "LOT_SIZE", "stepSize": "0.001", "minQty": "0.005"},
                    {"filterType": "MIN_NOTIONAL", "notional": "5.0"}
                ]
            }
        ]
    })
    return service


def test_valid_order_passes(exchange_info_service: ExchangeInfoService):
    request = OrderRequest(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("0.006"),
        price=Decimal("108000.10"),
    )
    # Should not raise
    exchange_info_service.validate_order(request)


def test_invalid_symbol_raises(exchange_info_service: ExchangeInfoService):
    request = OrderRequest(
        symbol="ETHUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("1.0"),
    )
    with pytest.raises(TradingBotError, match="Symbol ETHUSDT not found"):
        exchange_info_service.validate_order(request)


def test_quantity_below_min_qty_raises(exchange_info_service: ExchangeInfoService):
    request = OrderRequest(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.004"), # less than 0.005 minQty
    )
    with pytest.raises(InvalidParameterError, match="must be >= minQty"):
        exchange_info_service.validate_order(request)


def test_quantity_invalid_step_size_raises(exchange_info_service: ExchangeInfoService):
    request = OrderRequest(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.0055"), # not a multiple of 0.001 stepSize
    )
    with pytest.raises(InvalidParameterError, match="must be a multiple of stepSize"):
        exchange_info_service.validate_order(request)


def test_price_invalid_tick_size_raises(exchange_info_service: ExchangeInfoService):
    request = OrderRequest(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("0.005"),
        price=Decimal("108000.15"), # tick size is 0.10
    )
    with pytest.raises(InvalidParameterError, match="must be a multiple of tickSize"):
        exchange_info_service.validate_order(request)


def test_notional_below_min_notional_raises(exchange_info_service: ExchangeInfoService):
    request = OrderRequest(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("0.005"),
        price=Decimal("10.00"), # 0.005 * 10 = 0.05 < 5.0 minNotional
    )
    with pytest.raises(InvalidParameterError, match="Notional value"):
        exchange_info_service.validate_order(request)
