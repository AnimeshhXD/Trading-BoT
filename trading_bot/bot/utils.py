"""
utils.py — Formatting and display helpers for the CLI layer.

Design
------
Pure functions that format data for human consumption.  No business logic,
no Binance API calls, no side effects beyond writing to stdout.

Keeping display logic here (rather than in cli.py) means:
  - cli.py stays thin — just wiring, not formatting
  - These helpers are individually testable
  - A future web UI / API could reuse the formatters

Color scheme uses Typer's built-in ``typer.style`` which wraps ANSI codes,
ensuring they degrade gracefully on terminals that don't support color.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

import typer

from bot.constants import APP_BANNER, DIVIDER_NARROW, DIVIDER_WIDE
from bot.models import OrderRequest, OrderResponse


# ---------------------------------------------------------------------------
# Low-level display primitives
# ---------------------------------------------------------------------------


def print_wide_divider() -> None:
    """Print a wide ``=`` divider to stdout."""
    typer.echo(DIVIDER_WIDE)


def print_narrow_divider() -> None:
    """Print a narrow ``-`` divider to stdout."""
    typer.echo(DIVIDER_NARROW)


def print_banner() -> None:
    """Print the application banner block."""
    print_wide_divider()
    typer.echo(typer.style(APP_BANNER, fg=typer.colors.CYAN, bold=True))
    print_wide_divider()


def print_kv(label: str, value: str, *, label_width: int = 14) -> None:
    """Print a single key-value row aligned to a fixed label width.

    Parameters
    ----------
    label:
        The field name (left column).
    value:
        The field value (right column).
    label_width:
        Width to which the label is padded for alignment.
    """
    formatted_label = typer.style(f"{label:<{label_width}}", fg=typer.colors.WHITE)
    typer.echo(f"  {formatted_label}  {value}")


# ---------------------------------------------------------------------------
# Structured order display
# ---------------------------------------------------------------------------


def print_order_summary(request: OrderRequest) -> None:
    """Print a formatted summary of the order about to be submitted.

    Parameters
    ----------
    request:
        The validated ``OrderRequest`` built by the CLI.
    """
    typer.echo("")
    typer.echo(typer.style("  Order Summary", fg=typer.colors.BRIGHT_WHITE, bold=True))
    typer.echo("")

    print_kv("Symbol", request.symbol)
    print_kv("Side", _colour_side(request.side.value))
    print_kv("Type", request.order_type.name.replace("_", " "))
    print_kv("Quantity", str(request.quantity))

    if request.price is not None:
        print_kv("Price", f"{request.price:,.2f}")

    if request.stop_price is not None:
        print_kv("Stop Price", f"{request.stop_price:,.2f}")

    typer.echo("")


def print_order_response(response: OrderResponse) -> None:
    """Print a formatted table of the Binance order response.

    Parameters
    ----------
    response:
        The typed ``OrderResponse`` returned by ``OrderService``.
    """
    typer.echo(typer.style("  Response", fg=typer.colors.BRIGHT_WHITE, bold=True))
    typer.echo("")

    print_kv("Order ID", str(response.order_id))
    print_kv("Status", _colour_status(response.status.value))
    print_kv("Executed Qty", str(response.executed_qty))
    print_kv("Average Price", _format_price(response.avg_price))

    typer.echo("")


def print_success(message: str = "Order submitted successfully.") -> None:
    """Print a green success block.

    Parameters
    ----------
    message:
        The success message to display.
    """
    print_wide_divider()
    typer.echo(typer.style("  ✓  SUCCESS", fg=typer.colors.GREEN, bold=True))
    typer.echo(f"  {message}")
    print_wide_divider()


def print_error(message: str) -> None:
    """Print a red error block.

    Parameters
    ----------
    message:
        The human-readable error description.
    """
    print_wide_divider()
    typer.echo(typer.style("  ✗  ERROR", fg=typer.colors.RED, bold=True))
    typer.echo(f"  {message}")
    print_wide_divider()


def print_submitting() -> None:
    """Print the 'submitting order' separator."""
    print_narrow_divider()
    typer.echo(typer.style("  Submitting order...", fg=typer.colors.YELLOW))
    print_narrow_divider()


# ---------------------------------------------------------------------------
# Private formatting helpers
# ---------------------------------------------------------------------------


def _colour_side(side: str) -> str:
    """Return a colour-coded string for BUY (green) or SELL (red)."""
    if side == "BUY":
        return typer.style("BUY", fg=typer.colors.GREEN, bold=True)
    return typer.style("SELL", fg=typer.colors.RED, bold=True)


def _colour_status(status: str) -> str:
    """Return a colour-coded string for the order status."""
    colour_map: dict[str, str] = {
        "NEW": typer.colors.YELLOW,
        "PARTIALLY_FILLED": typer.colors.CYAN,
        "FILLED": typer.colors.GREEN,
        "CANCELED": typer.colors.RED,
        "REJECTED": typer.colors.RED,
        "EXPIRED": typer.colors.BRIGHT_BLACK,
        "EXPIRED_IN_MATCH": typer.colors.BRIGHT_BLACK,
    }
    colour = colour_map.get(status, typer.colors.WHITE)
    return typer.style(status, fg=colour, bold=True)


def _format_price(price: Decimal) -> str:
    """Return a human-readable price string; ``'0'`` for zero fills."""
    if price == Decimal("0"):
        return "0"
    return str(price.normalize())
