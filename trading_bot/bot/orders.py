"""
orders.py — OrderService: the business logic layer.

Design
------
``OrderService`` sits between the CLI and ``BinanceClient``:

    CLI  →  OrderService  →  BinanceClient  →  Binance API

Responsibilities
----------------
- Accepting an ``OrderRequest`` from the CLI.
- Running full validation via ``validate_order_request``.
- Injecting cross-cutting concerns (``time_in_force``, logging context).
- Dispatching to the correct ``BinanceClient`` method based on order type.
- Returning a typed ``OrderResponse`` to the CLI.
- Logging structured order lifecycle events for audit trails.

What it does NOT do
-------------------
- Does not call Binance directly (that is ``BinanceClient``'s job).
- Does not format output (that is ``utils.py``'s job).
- Does not parse CLI args (that is ``cli.py``'s job).

This separation means each layer can be tested and replaced independently.
"""

from __future__ import annotations

from bot.client import BinanceClient
from bot.constants import DEFAULT_TIME_IN_FORCE
from bot.exceptions import TradingBotError
from bot.exchange_info import ExchangeInfoService
from bot.logging_config import get_logger
from bot.models import OrderRequest, OrderResponse, OrderType
from bot.validators import validate_order_request

log = get_logger(__name__)


class OrderService:
    """Business logic orchestrator for order placement.

    Parameters
    ----------
    client:
        An initialised and connected ``BinanceClient`` instance.

    Example
    -------
    >>> client = BinanceClient()
    >>> client.connect()
    >>> service = OrderService(client)
    >>> response = service.place_order(request)
    """

    def __init__(self, client: BinanceClient) -> None:
        self._client = client
        self._exchange_info = ExchangeInfoService()
        self._exchange_info_loaded = False

    def place_order(self, request: OrderRequest) -> OrderResponse:
        """Validate and submit an order to Binance Futures.

        This is the single public entry point.  The CLI calls this; it never
        calls ``BinanceClient`` directly.

        Parameters
        ----------
        request:
            The ``OrderRequest`` constructed by the CLI.

        Returns
        -------
        OrderResponse
            Parsed, typed representation of the Binance confirmation.

        Raises
        ------
        ValidationError
            If any input field fails validation.
        BinanceApiError
            If Binance rejects the order (bad symbol, insufficient funds, …).
        NetworkError / TimeoutError
            If the exchange is unreachable.
        """
        log.info(
            "Order received | symbol={symbol} side={side} type={type} qty={qty}",
            symbol=request.symbol,
            side=request.side.value,
            type=request.order_type.name,
            qty=request.quantity,
        )

        # Step 1 — validate all fields before hitting the network (static rules)
        validate_order_request(request)
        
        # Step 2 — load exchange info and validate against dynamic trading rules
        if not self._exchange_info_loaded:
            log.debug("Loading exchange info for validation...")
            raw_info = self._client.get_exchange_info()
            self._exchange_info.load_from_api(raw_info)
            self._exchange_info_loaded = True
            
        self._exchange_info.validate_order(request)
        log.debug("Validation passed.")

        # Step 3 — inject time_in_force for order types that need it
        request = self._inject_time_in_force(request)

        # Step 4 — dispatch to the correct client method
        response = self._dispatch(request)

        log.info(
            "Order confirmed | order_id={oid} status={status} executed_qty={eq}",
            oid=response.order_id,
            status=response.status.value,
            eq=response.executed_qty,
        )

        return response

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _dispatch(self, request: OrderRequest) -> OrderResponse:
        """Route the request to the appropriate client method.

        Parameters
        ----------
        request:
            Validated, enriched ``OrderRequest``.

        Returns
        -------
        OrderResponse
            From the Binance client.

        Raises
        ------
        ValueError
            If an unrecognised order type slips through (programming error).
        """
        dispatch_map = {
            OrderType.MARKET: self._client.place_market_order,
            OrderType.LIMIT: self._client.place_limit_order,
            OrderType.STOP_LIMIT: self._client.place_stop_limit_order,
        }

        handler = dispatch_map.get(request.order_type)

        if handler is None:
            # Should never happen — validators catch unknown types first.
            raise ValueError(
                f"No handler registered for order type: {request.order_type!r}"
            )

        return handler(request)

    @staticmethod
    def _inject_time_in_force(request: OrderRequest) -> OrderRequest:
        """Return a new ``OrderRequest`` with ``time_in_force`` set if absent.

        MARKET orders do not use TIF; LIMIT and STOP_LIMIT default to GTC.

        Parameters
        ----------
        request:
            Original immutable ``OrderRequest``.

        Returns
        -------
        OrderRequest
            Either the same object (MARKET) or a new one with TIF populated.
        """
        if request.is_market() or request.time_in_force is not None:
            return request

        # ``dataclasses.replace`` creates a new frozen instance with one field
        # changed — respects immutability.
        from dataclasses import replace

        return replace(request, time_in_force=DEFAULT_TIME_IN_FORCE)
