"""
conftest.py — Shared pytest fixtures and test environment setup.

This file is automatically loaded by pytest before any test module runs.

Environment Patching
--------------------
``bot.config`` calls ``_load_settings()`` at import time, which raises
``AuthenticationError`` if API credentials are absent.

Since our unit tests mock ``BinanceClient`` and never hit the real API,
we patch the environment variables before any test import can trigger
the config module, ensuring offline tests work without a ``.env`` file.

Binance SDK Mocking
-------------------
``python-binance`` imports ``aiohttp`` (a C-extension) at package level.
On environments without MSVC Build Tools (e.g. Python 3.15 alpha on Windows)
``aiohttp`` cannot be compiled from source and no pre-built wheel exists yet.

Since all tests mock ``BinanceClient`` entirely, we register lightweight
``MagicMock`` stubs for the ``binance`` namespace in ``sys.modules`` before
any test module triggers the real import chain.
This keeps the test suite fully offline and build-tool agnostic.
"""

from __future__ import annotations

import os
import sys
from types import ModuleType
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# 1. Inject dummy credentials (must happen before bot.config is imported)
# ---------------------------------------------------------------------------

os.environ.setdefault("BINANCE_API_KEY", "test_api_key_placeholder")
os.environ.setdefault("BINANCE_API_SECRET", "test_api_secret_placeholder")

# ---------------------------------------------------------------------------
# 2. Stub the binance SDK so no aiohttp / C-extension is needed in tests.
#    The real BinanceClient is always replaced with MagicMock in test modules,
#    so these stubs only need to satisfy import resolution.
# ---------------------------------------------------------------------------


def _make_stub_module(name: str) -> ModuleType:
    """Return a MagicMock registered as a module under ``name``."""
    stub = MagicMock(spec=ModuleType(name))
    stub.__name__ = name
    stub.__spec__ = None
    return stub


_BINANCE_STUBS = [
    "aiohttp",
    "aiohttp.client",
    "binance",
    "binance.client",
    "binance.exceptions",
    "binance.async_client",
    "binance.streams",
]

for _mod_name in _BINANCE_STUBS:
    if _mod_name not in sys.modules:
        sys.modules[_mod_name] = _make_stub_module(_mod_name)

# Provide concrete exception classes that validators / client code reference.
import bot.exceptions as _exc  # noqa: E402 — must come after stubs

_binance_exc_stub = sys.modules["binance.exceptions"]
_binance_exc_stub.BinanceAPIException = type(
    "BinanceAPIException", (Exception,), {"status_code": 0, "message": ""}
)
_binance_exc_stub.BinanceRequestException = type("BinanceRequestException", (Exception,), {})

# Provide a Client class stub on the binance.client stub
_binance_client_stub = sys.modules["binance.client"]
_binance_client_stub.Client = MagicMock

