"""
client.py — BinanceClient: a thin, typed wrapper around python-binance.

Design
------
``BinanceClient`` is the **only** module that directly calls the Binance SDK.
Every other module that needs exchange data goes through this class.

Responsibilities
----------------
- Establishing and validating the SDK connection (``connect`` / ``ping``).
- Translating ``OrderRequest`` dataclasses into SDK keyword arguments.
- Translating raw SDK response dicts into ``OrderResponse`` dataclasses.
- Mapping python-binance exceptions to our custom exception hierarchy so the
  rest of the app never has to import from ``binance.exceptions``.
- Logging the full request payload and response at DEBUG level for auditing.

Why not inherit from the SDK client?
-------------------------------------
Composition over inheritance.  The SDK's ``Client`` has dozens of public
methods we don't expose.  Wrapping it keeps our interface minimal and makes
the class trivially mockable in tests.
"""

from __future__ import annotations

import socket
import time
from typing import Optional

from binance.client import Client as _BinanceSDKClient
from binance.exceptions import BinanceAPIException, BinanceRequestException

from bot.config import get_settings
from bot.constants import DEFAULT_TIME_IN_FORCE
from bot.exceptions import (
    AuthenticationError,
    BinanceApiError,
    BinanceRequestError,
    NetworkError,
    TimeoutError,
)
from bot.logging_config import get_logger
from bot.models import OrderRequest, OrderResponse, OrderType

log = get_logger(__name__)


class BinanceClient:
    """Thin, typed wrapper around the python-binance ``Client``.

    Instantiate once and share the instance across the application via
    ``OrderService``.  Call ``connect()`` before placing any orders.

    Example
    -------
    >>> client = BinanceClient()
    >>> client.connect()
    >>> response = client.place_market_order(request)
    """

    def __init__(self) -> None:
        self._sdk: Optional[_BinanceSDKClient] = None

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Initialise the SDK client and verify connectivity with a ping.

        Raises
        ------
        AuthenticationError
            If the SDK cannot authenticate with the provided credentials.
        NetworkError
            If no network path to the testnet exists.
        """
        log.info("Connecting to Binance Futures Testnet...")

        settings = get_settings()
        try:
            self._sdk = _BinanceSDKClient(
                api_key=settings.api_key,
                api_secret=settings.api_secret,
                testnet=settings.use_testnet,
                requests_params={"timeout": settings.request_timeout},
            )

            # Force python-binance to use Binance's CURRENT Futures Testnet REST endpoint.
            # Official base URL:
            # https://demo-fapi.binance.com/fapi
            self._sdk.API_URL = "https://demo-fapi.binance.com/fapi"
            self._sdk.FUTURES_URL = "https://demo-fapi.binance.com/fapi"
            print("\n========== BINANCE SDK ==========")
            print("USE_TESTNET :", settings.use_testnet)
            print("API_URL     :", self._sdk.API_URL)
            print("FUTURES_URL :", self._sdk.FUTURES_URL)
            print("================================\n")
            self.ping()
            log.info("Connected successfully to {url}", url=settings.base_url)

        except BinanceAPIException as exc:
            log.error("Authentication failed: {msg}", msg=exc.message)
            raise AuthenticationError() from exc

        except (socket.gaierror, ConnectionError) as exc:
            log.error("Network error during connect: {exc}", exc=str(exc))
            raise NetworkError(
                "Cannot reach Binance Testnet. Check your internet connection."
            ) from exc

    def ping(self) -> None:
        """Send a lightweight ping to verify the exchange is reachable.

        Raises
        ------
        NetworkError
            If the ping fails for any reason.
        """
        sdk = self._get_sdk()
        try:
            sdk.ping()
            log.debug("Ping successful.")
        except Exception as exc:
            raise NetworkError(f"Ping failed: {exc}") from exc

    def get_account(self) -> dict:
        """Fetch futures account information.

        Returns
        -------
        dict
            Raw account data dict from Binance (balances, positions, etc.).

        Raises
        ------
        BinanceApiError
            On API-level failures.
        """
        sdk = self._get_sdk()
        log.debug("Fetching futures account info...")

        try:
            response: dict = sdk.futures_account()
            log.debug("Account info fetched successfully.")
            return response

        except BinanceAPIException as exc:
            raise self._wrap_api_exception(exc) from exc

    def get_exchange_info(self) -> dict:
        """Fetch futures exchange info containing symbol trading rules.

        Returns
        -------
        dict
            Raw exchange info data from Binance.
        """
        sdk = self._get_sdk()
        log.debug("Fetching futures exchange info...")

        try:
            return sdk.futures_exchange_info()
        except BinanceAPIException as exc:
            raise self._wrap_api_exception(exc) from exc

    # ------------------------------------------------------------------
    # Order placement
    # ------------------------------------------------------------------

    def place_market_order(self, request: OrderRequest) -> OrderResponse:
        """Place a MARKET order on Binance Futures."""
        self._assert_connected()
        settings = get_settings()

        payload = {
            "symbol": request.symbol,
            "side": request.side.value,
            "type": OrderType.MARKET.value,
            "quantity": str(request.quantity),
            "recvWindow": settings.recv_window,
        }

        log.debug("Placing MARKET order | payload={payload}", payload=payload)
        self._log_before_binance_call(endpoint="futures_create_order", payload=payload)
        raw = self._execute_order(payload)
        return OrderResponse.from_api_response(raw)

    def place_limit_order(self, request: OrderRequest) -> OrderResponse:
        """Place a LIMIT order on Binance Futures."""
        self._assert_connected()
        settings = get_settings()

        tif = request.time_in_force or DEFAULT_TIME_IN_FORCE
        payload = {
            "symbol": request.symbol,
            "side": request.side.value,
            "type": OrderType.LIMIT.value,
            "quantity": str(request.quantity),
            "price": str(request.price),
            "timeInForce": tif,
            "recvWindow": settings.recv_window,
        }

        log.debug("Placing LIMIT order | payload={payload}", payload=payload)
        self._log_before_binance_call(endpoint="futures_create_order", payload=payload)
        raw = self._execute_order(payload)
        return OrderResponse.from_api_response(raw)

    def place_stop_limit_order(self, request: OrderRequest) -> OrderResponse:
        """Place a STOP-LIMIT order on Binance Futures."""
        self._assert_connected()
        settings = get_settings()

        tif = request.time_in_force or DEFAULT_TIME_IN_FORCE
        payload = {
            "symbol": request.symbol,
            "side": request.side.value,
            "type": OrderType.STOP_LIMIT.value,  # sends "STOP" to Binance
            "quantity": str(request.quantity),
            "price": str(request.price),
            "stopPrice": str(request.stop_price),
            "timeInForce": tif,
            "recvWindow": settings.recv_window,
        }

        log.debug("Placing STOP-LIMIT order | payload={payload}", payload=payload)
        self._log_before_binance_call(endpoint="futures_create_order", payload=payload)
        raw = self._execute_order(payload)
        return OrderResponse.from_api_response(raw)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _log_before_binance_call(self, endpoint: str, payload: dict) -> None:
        settings = get_settings()
        current_ts_ms = int(time.time() * 1000)
        payload_types = {k: type(v).__name__ for k, v in payload.items()}

        block = (
            "\n========== REQUEST =========="
            "\n"
            f"Endpoint: {endpoint}\n"
            f"Timestamp(ms): {current_ts_ms}\n"
            f"recvWindow: {settings.recv_window}\n"
            f"use_testnet flag: {settings.use_testnet}\n"
            f"Payload: {payload}\n"
            f"Payload types: {payload_types}\n"
            "=============================\n"
        )
        print(block)
        log.debug(block)

    def _execute_order(self, payload: dict) -> dict:

        """Call the Binance futures new order endpoint and return the raw dict."""
        sdk = self._get_sdk()
        try:
            # Evidence-capture: print the exact URL the SDK issues.
            # We wrap the underlying requests session for this call only.
            session = getattr(sdk, "session", None)
            original_request = None

            if session is not None and hasattr(session, "request"):
                original_request = session.request

                def _debug_request(method, url, *args, **kwargs):
                    try:
                        print("\n========== SDK HTTP REQUEST ==========")
                        print("Method:", method)
                        print("Full URL:", url)
                        print("Kwargs keys:", list(kwargs.keys()))
                        print("========================================\n")
                    except Exception:
                        pass
                    return original_request(method, url, *args, **kwargs)

                session.request = _debug_request  # type: ignore[assignment]

            response: dict = sdk.futures_create_order(**payload)


            print("\n========== RAW RESPONSE ==========")
            print(response)
            print("==================================\n")
            log.debug("Order response | response={response}", response=response)
            return response

        except BinanceAPIException as exc:
            import traceback

            print("\n========== BINANCE API ERROR ==========")
            print("HTTP Status Code :", getattr(exc, "status_code", None))
            print("Error Code        :", getattr(exc, "code", None))
            print("Error Message    :", getattr(exc, "message", None))
            print("Response Body (if available):", getattr(exc, "response", None))
            print("Request Payload  :", payload)
            print("\nFull traceback:")
            traceback.print_exc()
            print("========================================\n")

            log.error(
                "Binance API error | status={status} code={code} msg={msg} payload={payload}",
                status=getattr(exc, "status_code", None),
                code=getattr(exc, "code", None),
                msg=getattr(exc, "message", None),
                payload=payload,
            )
            # Restore wrapped session.request if we replaced it
            try:
                if session is not None and original_request is not None and hasattr(session, "request"):
                    session.request = original_request  # type: ignore[assignment]
            except Exception:
                pass

            raise self._wrap_api_exception(exc) from exc

        except BinanceRequestException as exc:

            import traceback

            print("\n========== BINANCE REQUEST ERROR ==========")
            print("Complete exception:", repr(exc))
            print("Payload:", payload)
            print("\nTraceback:")
            traceback.print_exc()
            print("============================================\n")

            log.error(
                "Binance request error | exc={exc} payload={payload}",
                exc=str(exc),
                payload=payload,
            )
            raise BinanceRequestError(str(exc)) from exc

        except TimeoutError:
            log.error("Request timed out.")
            raise TimeoutError() from None

        except (socket.gaierror, ConnectionError) as exc:
            import traceback

            print("\n========== NETWORK ERROR ==========")
            print("Type(exception):", type(exc).__name__)
            print("repr(exception) :", repr(exc))
            print("str(exception)  :", str(exc))
            print("Payload          :", payload)
            print("\nFull traceback:")
            traceback.print_exc()
            print("===================================\n")

            log.error("Network error | exc={exc} payload={payload}", exc=str(exc), payload=payload)
            raise NetworkError(f"Network error: {exc}") from exc

        except Exception as exc:
            import traceback

            print("\n========== ANY EXCEPTION ==========")
            print("type(exception):", type(exc).__name__)
            print("repr(exception):", repr(exc))
            print("str(exception):", str(exc))
            print("Payload:", payload)
            print("\nFull traceback:")
            traceback.print_exc()
            print("===================================\n")

            log.exception(
                "Unexpected exception in _execute_order | payload={payload} exc={exc}",
                payload=payload,
                exc=str(exc),
            )
            raise

    def _get_sdk(self) -> _BinanceSDKClient:
        """Return the connected SDK instance."""
        self._assert_connected()
        assert self._sdk is not None
        return self._sdk

    def _assert_connected(self) -> None:
        if self._sdk is None:
            raise RuntimeError(
                "BinanceClient is not connected. Call connect() before placing orders."
            )

    @staticmethod
    def _wrap_api_exception(exc: BinanceAPIException) -> BinanceApiError:
        return BinanceApiError(code=exc.status_code, message=exc.message)
