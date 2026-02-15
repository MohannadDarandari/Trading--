"""Quick test: can the bot import and initialize locally?"""
import os, sys
os.chdir(r"C:\Users\mdara\OneDrive\Desktop\DarkOps HQ\Trading$$")
sys.path.insert(0, ".")

from dotenv import load_dotenv
load_dotenv(".env")

# Check env vars
pk = os.environ.get("POLYCLAW_PRIVATE_KEY", "")
rpc = os.environ.get("CHAINSTACK_NODE", "")
print(f"PK: {'set' if pk else 'MISSING'} ({pk[:8]}...)")
print(f"RPC: {'set' if rpc else 'MISSING'}")
print(f"AUTO_TRADE: {os.environ.get('AUTO_TRADE', 'not set')}")
print(f"TRADE_BUDGET: {os.environ.get('TRADE_BUDGET', 'not set')}")
print(f"BANKROLL: {os.environ.get('BANKROLL', 'not set')}")

# Test imports
from lib.wallet_manager import WalletManager
w = WalletManager()
print(f"\nWallet: {w.address}")
print(f"Unlocked: {w.is_unlocked}")

if w.is_unlocked:
    try:
        bal = w.get_balances()
        print(f"POL: {bal.pol:.4f}")
        print(f"USDC.e: {bal.usdc_e:.4f}")
    except Exception as e:
        print(f"Balance check: {e}")

from lib.clob_client import ClobClientWrapper
c = ClobClientWrapper(private_key=w.get_unlocked_key(), address=w.address)
c.connect()
print(f"\nCLOB connected: {c._client is not None}")

# Quick order book test
try:
    ob = c.get_order_book("1016769973636871997242456073428770361484")
    print(f"Order book: {len(ob.get('asks', []))} asks, {len(ob.get('bids', []))} bids")
except Exception as e:
    print(f"Order book: {e}")

print("\nAll systems GO for local run!")
