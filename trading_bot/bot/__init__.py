"""
bot package — core trading engine for the Binance Futures Testnet CLI.

Sub-modules
-----------
exceptions      : Domain-specific exception hierarchy.
constants       : All application-wide literals and defaults.
models          : Enums and dataclasses (OrderSide, OrderType, …).
config          : Environment variable loading via python-dotenv.
logging_config  : Loguru setup — console + rotating file handler.
validators      : Reusable, stateless input validation functions.
utils           : Formatting and display helpers.
client          : BinanceClient wrapper around python-binance.
orders          : OrderService — business logic layer.
"""
