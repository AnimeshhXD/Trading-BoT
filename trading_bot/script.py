from dotenv import load_dotenv
from binance.client import Client
import os

load_dotenv()

client = Client(
    api_key=os.getenv("BINANCE_API_KEY"),
    api_secret=os.getenv("BINANCE_API_SECRET"),
    testnet=True,
)

print("Testing Spot Ping...")
print(client.ping())

print("\nTesting Futures Account...")
try:
    account = client.futures_account()
    print("SUCCESS")
    print(account)
except Exception as e:
    print(f"ERROR: {type(e).__name__}")
    print(e)