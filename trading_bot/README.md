# Binance Futures Trading Bot

A production-quality Python CLI application for placing orders on the **Binance Futures Testnet (USDT-M)**.

Built to demonstrate professional-grade Python engineering practices: clean architecture, SOLID principles, full type safety, structured logging, and comprehensive error handling — exactly the patterns expected at a quantitative trading firm.

---

## Features

| Feature | Detail |
|---------|--------|
| **Order Types** | MARKET, LIMIT, STOP-LIMIT |
| **Sides** | BUY, SELL |
| **Architecture** | Layered: CLI → Service → Client → Exchange |
| **Logging** | Loguru — rotating file + coloured console |
| **Validation** | Stateless validators, custom exception hierarchy |
| **Type Safety** | Full type hints + `Final` constants + `frozen` dataclasses |
| **Testing** | pytest unit tests for validators and OrderService |
| **Configuration** | python-dotenv — credentials never hardcoded |

---

## Project Structure

```
trading_bot/
│
├── bot/
│   ├── __init__.py          # Package docstring
│   ├── client.py            # BinanceClient — only layer that calls Binance SDK
│   ├── orders.py            # OrderService — business logic orchestration
│   ├── validators.py        # Pure stateless validation functions
│   ├── exceptions.py        # Domain exception hierarchy
│   ├── config.py            # Settings loaded from .env via python-dotenv
│   ├── constants.py         # All literals — URLs, defaults, display strings
│   ├── models.py            # Enums (OrderSide, OrderType, OrderStatus) + Dataclasses
│   ├── logging_config.py    # Loguru setup — dual sink (console + rotating file)
│   └── utils.py             # CLI display helpers — print_order_summary, print_error …
│
├── logs/                    # Auto-created; trading.log rotates at 5 MB
│
├── tests/
│   ├── __init__.py
│   ├── test_validators.py   # 20+ pure unit tests for all validators
│   └── test_orders.py       # OrderService tests with mock BinanceClient
│
├── cli.py                   # Typer entry point — thin, no business logic
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
└── LICENSE
```

---

## Installation

**1. Clone the repository**

```bash
git clone https://github.com/your-username/binance-futures-bot.git
cd binance-futures-bot/trading_bot
```

**2. Create and activate a virtual environment**

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

**3. Install dependencies**

```bash
pip install -r requirements.txt
```

**4. Configure environment variables**

Follow the detailed instructions in the [Environment Setup](#environment-setup) section below to create and fill in your `.env` file.

---

## Environment Setup

The application is driven by environment variables defined in a `.env` file at the root of the project. Follow these steps to configure your environment:

1. **Copy the example configuration file:**
   Duplicate the `.env.example` file in the project root and rename it to `.env`:
   ```bash
   cp .env.example .env
   ```
   *(On Windows Command Prompt, use `copy .env.example .env`. On PowerShell, use `Copy-Item .env.example .env`)*

2. **Paste your Binance Futures Testnet API Key:**
   Open the `.env` file in your editor and paste your Binance Futures Testnet API key next to `BINANCE_API_KEY=`.
   - **Where to obtain:** Register at [https://testnet.binancefuture.com](https://demo.binance.com/en/futures/BTCUSDT) and click on the "API Key" button to generate your keys.

3. **Paste your Secret Key:**
   Paste your Binance Futures Testnet API secret key next to `BINANCE_API_SECRET=`.
   - **Where to obtain:** Provided along with the API Key when you generate it on the Binance Futures Testnet portal. Keep this secret and secure.

4. **Understand the USE_TESTNET toggle:**
   `USE_TESTNET` determines whether the trading bot connects to the Binance Futures Testnet or the Production exchange.
   - Set to `true` (default) to connect to the Testnet environment (safe for testing).
   - Set to `false` if you intend to connect to the Live/Production Binance Futures exchange.

The application will **refuse to start** if any required variable is missing or if `USE_TESTNET` is not a valid boolean, displaying a clear authentication/validation error.

---

## Usage

All commands are run from the `trading_bot/` directory.

### Check connectivity

```bash
python cli.py ping
```

### View help

```bash
python cli.py --help
python cli.py order --help
```

---

### Place a MARKET Order

```bash
python cli.py order \
  --symbol BTCUSDT \
  --side BUY \
  --type MARKET \
  --quantity 0.001
```

**Expected output:**

```
==================================================
BINANCE FUTURES TESTNET
==================================================

  Order Summary

  Symbol          BTCUSDT
  Side            BUY
  Type            MARKET
  Quantity        0.001

--------------------------------------------------
  Submitting order...
--------------------------------------------------
  Response

  Order ID        12345678
  Status          NEW
  Executed Qty    0.0
  Average Price   0

==================================================
  ✓  SUCCESS
  Order submitted successfully.
==================================================
```

---

### Place a LIMIT Order

```bash
python cli.py order \
  --symbol BTCUSDT \
  --side SELL \
  --type LIMIT \
  --price 108000 \
  --quantity 0.001
```

---

### Place a STOP-LIMIT Order

```bash
python cli.py order \
  --symbol BTCUSDT \
  --side BUY \
  --type STOP_LIMIT \
  --price 108500 \
  --stop-price 108000 \
  --quantity 0.001
```

> **Note on STOP-LIMIT**: `--price` is the limit execution price; `--stop-price` is the trigger. Binance Futures will activate the order when the market reaches `--stop-price`, then attempt to fill at `--price`.
>
> **Status**: STOP-LIMIT is implemented, but it is **not working** end-to-end in this project at the moment.
>
> Under the hood, `python-binance==1.0.37` routes conditional `type="STOP"` orders to the **algo conditional endpoint** (`/fapi/v1/algoOrder`) and renames the payload field **`stopPrice` → `triggerPrice`**.
> If Binance rejects your request, this SDK transformation is the first thing to check when debugging.


---

### View Account Balances

```bash
python cli.py account
```

---

## Running Tests

```bash
# All tests
pytest tests/ -v

# With coverage report
pytest tests/ -v --cov=bot --cov-report=term-missing

# Validators only
pytest tests/test_validators.py -v

# OrderService only
pytest tests/test_orders.py -v
```

All tests run **offline** — no Binance credentials or network access required. The `OrderService` tests mock `BinanceClient` entirely.

---

## Logging

| Sink | Level | Location | Format |
|------|-------|----------|--------|
| Console | INFO+ | `stderr` | Concise, coloured |
| File | DEBUG+ | `logs/trading.log` | Full context + timestamps |

**Log rotation**: Automatically at 5 MB, compressed to `.zip`, retained for 10 days.

**What is logged:**
- Every order request (symbol, side, type, quantity)
- Full API payload at DEBUG level
- Full API response at DEBUG level
- Every error with stack trace
- Connection events (connect, ping)

---

## Architecture Decisions

### Layered Architecture
- **`OrderService`**: Orchestrates validation (both static rules and dynamic `ExchangeInfoService` rules) and dependency injection.
- **`ExchangeInfoService`**: Downloads `/fapi/v1/exchangeInfo` and caches it to enforce true `tickSize` and `stepSize` filters before orders reach Binance.
- **`BinanceClient`**: A thin adapter wrapping the `python-binance` SDK, handling network errors and JSON translation.

### 4. Precision Financial Data (`decimal.Decimal`)
Production systems avoid binary floating point for financial calculations. This codebase exclusively uses `decimal.Decimal` to construct `OrderRequest` and `OrderResponse` models, guaranteeing zero precision loss and accurately serializing to strings required by Binance's strict step sizes.

### 5. Robust Type Hierarchy
All exceptions inherit from `TradingBotError`. This lets callers be as specific (`except BinanceApiError`) or as broad (`except TradingBotError`) as their context requires.

### Frozen Dataclasses
`OrderRequest` and `OrderResponse` are `frozen=True`. Once built by the CLI, the payload cannot be mutated by any layer — preventing subtle bugs where the service modifies an object the CLI still holds a reference to.

### `str, Enum` Mixin
`OrderSide("BUY")` and `OrderType("STOP")` are both valid strings. python-binance accepts them directly without `.value` lookups, keeping call sites clean.

### `Final` Constants
Every magic string, URL, and default uses `typing.Final`. Type checkers (mypy, pyright) flag any accidental reassignment at analysis time, not runtime.

---

## Assumptions

1. **Testnet only** — The `testnet=True` flag is hardcoded in `BinanceClient`. Switching to mainnet requires changing this flag and updating `TESTNET_BASE_URL` in `constants.py`.
2. **USDT-M Futures** — All symbols are assumed to be linear perpetual contracts (USDT-margined). Coin-margined (COIN-M) contracts are not tested.
3. **Single-threaded** — The application is synchronous. For high-frequency use, consider adding async support via `python-binance`'s websocket streams.
4. **No position management** — This bot places orders only. Open position tracking, PnL calculation, and risk management are out of scope.

---

## Future Improvements

- [ ] **Async support** — Replace the synchronous SDK with `AsyncClient` for non-blocking I/O.
- [ ] **WebSocket streams** — Live order book and position updates via Binance user data stream.
- [ ] **Order management** — `cancel`, `status`, and `list-open` commands.
- [ ] **Risk management** — Maximum position size, daily loss limit enforcement.
- [ ] **Strategy layer** — Abstract `Strategy` interface with a simple moving average example.
- [ ] **Configuration file** — YAML/TOML config for default symbols, quantities, and TIF.
- [ ] **Docker support** — `Dockerfile` and `docker-compose.yml` for containerised deployment.
- [ ] **CI/CD pipeline** — GitHub Actions workflow for lint, type-check, and test on every push.
- [ ] **Integration tests** — Testnet integration tests gated behind an environment flag.

---


## License

MIT — see [LICENSE](LICENSE).
