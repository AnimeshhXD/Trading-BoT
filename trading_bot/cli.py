"""
cli.py — Typer-powered command-line interface for the Binance Futures trading bot.

Design
------
The CLI is the application's entry point and is intentionally thin:

  1. Parse and coerce raw user input into typed values.
  2. Build an ``OrderRequest`` dataclass.
  3. Hand it to ``OrderService.place_order()``.
  4. Display the ``OrderResponse`` via ``utils`` helpers.
  5. Handle every exception category with a clean, coloured message.

The CLI *never* calls Binance directly, *never* contains business logic, and
*never* formats data inline — each of those concerns lives in its own module.

Usage
-----
    python cli.py order --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001
    python cli.py order --symbol BTCUSDT --side SELL --type LIMIT --price 108000 --quantity 0.001
    python cli.py order --symbol BTCUSDT --side BUY --type STOP_LIMIT --price 108500 --stop-price 108000 --quantity 0.001
    python cli.py ping
    python cli.py account
"""

from __future__ import annotations

import sys
from decimal import Decimal
from typing import Optional

import typer
from typing_extensions import Annotated

from bot.client import BinanceClient
from bot.exceptions import (
    BinanceApiError,
    BinanceRequestError,
    NetworkError,
    TradingBotError,
    TimeoutError,
    ValidationError,
)
from bot.logging_config import get_logger, setup_logging
from bot.models import OrderRequest, OrderSide, OrderType
from bot.orders import OrderService
from bot.utils import (
    print_banner,
    print_error,
    print_narrow_divider,
    print_order_response,
    print_order_summary,
    print_submitting,
    print_success,
    print_wide_divider,
)

# ---------------------------------------------------------------------------
# App bootstrap
# ---------------------------------------------------------------------------

setup_logging()
log = get_logger(__name__)

app = typer.Typer(
    name="trading-bot",
    help="Binance Futures Testnet trading CLI.",
    rich_markup_mode="rich",
    no_args_is_help=True,
    add_completion=False,
)


# ---------------------------------------------------------------------------
# Shared client / service factory
# ---------------------------------------------------------------------------


def _build_service() -> OrderService:
    """Create, connect, and return an ``OrderService`` instance.

    Centralised so ``order``, ``ping``, and ``account`` commands all go
    through the same initialisation path.

    Raises
    ------
    SystemExit
        Exits with code 1 if connection fails, after showing a clean message.
    """
    client = BinanceClient()
    try:
        client.connect()
    except TradingBotError as exc:
        print_error(exc.message)
        log.error("Connection failed: {msg}", msg=exc.message)
        raise typer.Exit(code=1) from exc
    return OrderService(client)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command(name="order", help="Place a futures order on Binance Testnet.")
def place_order(
    symbol: Annotated[
        str,
        typer.Option(
            "--symbol", "-s",
            help="Trading pair symbol, e.g. [cyan]BTCUSDT[/cyan].",
            show_default=False,
        ),
    ],
    side: Annotated[
        OrderSide,
        typer.Option(
            "--side",
            help="Order direction: [green]BUY[/green] or [red]SELL[/red].",
            show_default=False,
            case_sensitive=False,
        ),
    ],
    order_type: Annotated[
        str,
        typer.Option(
            "--type", "-t",
            help="Order type: [bold]MARKET[/bold], [bold]LIMIT[/bold], or [bold]STOP_LIMIT[/bold].",
            show_default=False,
        ),
    ],
    quantity: Annotated[
        str,
        typer.Option(
            "--quantity", "-q",
            help="Number of contracts to trade. Must be > 0.",
            show_default=False,
        ),
    ],
    price: Annotated[
        Optional[str],
        typer.Option(
            "--price", "-p",
            help="Limit price. Required for LIMIT and STOP_LIMIT orders.",
            show_default=False,
        ),
    ] = None,
    stop_price: Annotated[
        Optional[str],
        typer.Option(
            "--stop-price",
            help="Stop trigger price. Required for STOP_LIMIT orders.",
            show_default=False,
        ),
    ] = None,
) -> None:
    """Validate inputs, build an order request, and submit to Binance."""

    print_banner()

    # --- Map the user-facing type string to an OrderType enum --------------
    normalised_type = order_type.upper().replace("-", "_")
    try:
        parsed_type = _parse_order_type(normalised_type)
    except ValueError:
        print_error(
            f"Unknown order type '{order_type}'. "
            "Valid options: MARKET, LIMIT, STOP_LIMIT"
        )
        raise typer.Exit(code=1)

    # --- Parse numeric strings to exact Decimals ---------------------------
    try:
        qty_dec = Decimal(quantity)
        price_dec = Decimal(price) if price is not None else None
        stop_price_dec = Decimal(stop_price) if stop_price is not None else None
    except Exception as exc:
        print_error(f"Invalid numeric format: {exc}")
        raise typer.Exit(code=1)

    # --- Build the typed request object ------------------------------------
    request = OrderRequest(
        symbol=symbol.upper().strip(),
        side=side,
        order_type=parsed_type,
        quantity=qty_dec,
        price=price_dec,
        stop_price=stop_price_dec,
    )

    # --- Display summary then submit ---------------------------------------
    print_order_summary(request)
    print_submitting()

    service = _build_service()

    try:
        response = service.place_order(request)

    except ValidationError as exc:
        print_error(exc.message)
        log.warning("Validation error: {msg}", msg=exc.message)
        raise typer.Exit(code=1)

    except BinanceApiError as exc:
        print_error(exc.message)
        log.error("Binance API error: {msg}", msg=exc.message)
        raise typer.Exit(code=1)

    except BinanceRequestError as exc:
        print_error(exc.message)
        log.error("Binance request error: {msg}", msg=exc.message)
        raise typer.Exit(code=1)

    except (TimeoutError, NetworkError) as exc:
        print_error(exc.message)
        log.error("Network error: {msg}", msg=exc.message)
        raise typer.Exit(code=1)

    except TradingBotError as exc:
        # Catch-all for any other domain exceptions
        print_error(exc.message)
        log.error("Unexpected trading error: {msg}", msg=exc.message)
        raise typer.Exit(code=1)

    except Exception as exc:  # noqa: BLE001
        # True unexpected errors — log full traceback, show clean message
        log.exception("Unexpected exception: {exc}", exc=str(exc))
        print_error("An unexpected error occurred. Check logs/trading.log for details.")
        raise typer.Exit(code=1)

    # --- Show result -------------------------------------------------------
    print_order_response(response)
    print_success()


@app.command(name="ping", help="Check connectivity to Binance Futures Testnet.")
def ping() -> None:
    """Send a ping to Binance and report latency."""
    print_banner()
    typer.echo(typer.style("  Pinging Binance Futures Testnet...", fg=typer.colors.CYAN))
    print_narrow_divider()

    try:
        client = BinanceClient()
        client.connect()
        typer.echo(typer.style("  ✓  Exchange is reachable.", fg=typer.colors.GREEN, bold=True))
        log.info("Ping successful.")

    except TradingBotError as exc:
        print_error(exc.message)
        log.error("Ping failed: {msg}", msg=exc.message)
        raise typer.Exit(code=1)

    print_wide_divider()


@app.command(name="account", help="Display Binance Futures account balance summary.")
def account() -> None:
    """Fetch and display account assets with non-zero balance."""
    print_banner()
    typer.echo(typer.style("  Account Summary", fg=typer.colors.BRIGHT_WHITE, bold=True))
    print_narrow_divider()

    try:
        client = BinanceClient()
        client.connect()
        data = client.get_account()

    except TradingBotError as exc:
        print_error(exc.message)
        log.error("Account fetch failed: {msg}", msg=exc.message)
        raise typer.Exit(code=1)

    assets = [a for a in data.get("assets", []) if float(a.get("walletBalance", 0)) > 0]

    if not assets:
        typer.echo("  No assets with non-zero balance found.")
    else:
        for asset in assets:
            typer.echo(
                f"  {asset['asset']:<8}  "
                f"Wallet: {float(asset['walletBalance']):>12.4f}  "
                f"Available: {float(asset.get('availableBalance', 0)):>12.4f}"
            )

    print_wide_divider()


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _parse_order_type(raw: str) -> OrderType:
    """Map a normalised user-facing type string to an ``OrderType`` enum.

    Parameters
    ----------
    raw:
        Uppercased, underscore-normalised string from the CLI, e.g.
        ``"STOP_LIMIT"`` or ``"MARKET"``.

    Returns
    -------
    OrderType

    Raises
    ------
    ValueError
        If the string does not match any known ``OrderType``.
    """
    type_map: dict[str, OrderType] = {
        "MARKET": OrderType.MARKET,
        "LIMIT": OrderType.LIMIT,
        "STOP_LIMIT": OrderType.STOP_LIMIT,
        "STOP": OrderType.STOP_LIMIT,  # accept bare "STOP" as alias
    }

    result = type_map.get(raw)
    if result is None:
        raise ValueError(f"Unknown order type: {raw!r}")
    return result


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    app()
