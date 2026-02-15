"""Check actual fills, balances, and positions."""
import os, json, requests
os.chdir(r"C:\Users\mdara\OneDrive\Desktop\DarkOps HQ\Trading$$")
from dotenv import load_dotenv
load_dotenv()

from py_clob_client.client import ClobClient

PK = os.environ['POLYCLAW_PRIVATE_KEY']
ADDR = '0xAdd5cf1e1d6992C0130C3a89094F300fA71d32E5'

client = ClobClient(
    "https://clob.polymarket.com",
    key=PK,
    chain_id=137,
    signature_type=0,
    funder=ADDR,
)
creds = client.create_or_derive_api_creds()
client.set_api_creds(creds)

# Detailed trade info
print("=== DETAILED TRADES ===")
try:
    trades = client.get_trades()
    if isinstance(trades, list):
        for t in trades:
            print(json.dumps(t, indent=2))
            print("---")
except Exception as e:
    print(f"Error: {e}")

# Current USDC balance
print("\n=== WALLET BALANCE ===")
from lib.wallet_manager import WalletManager
w = WalletManager()
try:
    bal = w.get_balances()
    print(f"POL: {bal.pol:.4f}")
    print(f"USDC.e: {bal.usdc_e:.4f}")
except Exception as e:
    print(f"Balance error: {e}")

# Check CLOB balance (what Polymarket holds)
print("\n=== CLOB BALANCE ===")
try:
    r = requests.get(f"https://clob.polymarket.com/balances/{ADDR}")
    print(f"CLOB balances: {json.dumps(r.json())[:500]}")
except Exception as e:
    print(f"CLOB balance error: {e}")

# Check if this is a proper event group
print("\n=== FED RATES EVENT GROUP ===")
# Find the parent event that contains all outcomes
try:
    r = requests.get("https://gamma-api.polymarket.com/events?slug=fed-interest-rate-march-2026")
    data = r.json()
    if data:
        for event in (data if isinstance(data, list) else [data]):
            print(f"Event: {event.get('title', '')}")
            markets = event.get('markets', [])
            print(f"Total markets: {len(markets)}")
            total_price = 0
            for m in markets:
                p = float(m.get('outcomePrices', '[0,0]').strip('[]').split(',')[0])
                title = m.get('groupItemTitle', m.get('question', ''))[:50]
                mid = m.get('id', '')
                print(f"  [{mid}] {title}: ${p:.4f}")
                total_price += p
            print(f"\nTotal sum of 'Yes' prices: ${total_price:.4f}")
            print(f"If sum < $1: hedge is profitable. If outcomes aren't exhaustive: RISK!")
    else:
        # Try different slug
        r2 = requests.get("https://gamma-api.polymarket.com/markets?tag=fed-rates&limit=20&closed=false")
        data2 = r2.json()
        for m in data2[:10]:
            print(f"  {m.get('id','')} | {m.get('question','')[:60]}")
except Exception as e:
    print(f"Event error: {e}")
