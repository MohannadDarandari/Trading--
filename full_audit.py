"""Full audit: all trades, positions, balance, P&L."""
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

# 1. All trades
print("=" * 60)
print("ALL CONFIRMED TRADES")
print("=" * 60)
trades = client.get_trades()
total_spent = 0
positions = {}

if isinstance(trades, list):
    for t in trades:
        side = t.get('side', '')
        size = float(t.get('size', 0))
        price = float(t.get('price', 0))
        cost = size * price
        total_spent += cost
        asset = t.get('asset_id', '')[:20]
        market = t.get('market', '')[:20]
        outcome = t.get('outcome', '')
        status = t.get('status', '')
        tx = t.get('transaction_hash', '')[:20]
        
        # Track positions
        key = t.get('asset_id', '')
        if key not in positions:
            positions[key] = {'shares': 0, 'cost': 0, 'market': market, 'outcome': outcome, 'asset_short': asset}
        positions[key]['shares'] += size
        positions[key]['cost'] += cost
        
        print(f"  {side} {size:.2f} @ ${price:.4f} = ${cost:.4f} | {outcome} | {status} | tx:{tx}...")

print(f"\nTotal trades: {len(trades)}")
print(f"Total USDC spent: ${total_spent:.4f}")

# 2. Positions summary
print("\n" + "=" * 60)
print("CURRENT POSITIONS")
print("=" * 60)
for asset_id, pos in positions.items():
    print(f"  {pos['outcome']} | {pos['shares']:.2f} shares | cost: ${pos['cost']:.4f} | avg: ${pos['cost']/pos['shares']:.4f}/share")
    print(f"    Asset: {asset_id[:40]}...")

# 3. Wallet balance
print("\n" + "=" * 60)
print("WALLET BALANCE")
print("=" * 60)
from lib.wallet_manager import WalletManager
w = WalletManager()
try:
    bal = w.get_balances()
    print(f"  POL (gas): {bal.pol:.6f}")
    print(f"  USDC.e: {bal.usdc_e:.6f}")
except Exception as e:
    print(f"  Error: {e}")

# 4. Check on-chain positions via CTF
print("\n" + "=" * 60)
print("ON-CHAIN CTF POSITIONS")
print("=" * 60)
from web3 import Web3
w3 = Web3(Web3.HTTPProvider(os.environ.get("CHAINSTACK_NODE", "")))

CTF_ADDRESS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
CTF_ABI = [{"inputs":[{"name":"account","type":"address"},{"name":"id","type":"uint256"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"}]
ctf = w3.eth.contract(address=Web3.to_checksum_address(CTF_ADDRESS), abi=CTF_ABI)

for asset_id, pos in positions.items():
    try:
        balance = ctf.functions.balanceOf(Web3.to_checksum_address(ADDR), int(asset_id)).call()
        balance_shares = balance / 1e6  # USDC has 6 decimals
        print(f"  {pos['outcome']}: {balance_shares:.2f} shares on-chain (traded: {pos['shares']:.2f})")
    except Exception as e:
        print(f"  {pos['outcome']}: error checking - {str(e)[:60]}")

# 5. Open orders
print("\n" + "=" * 60)
print("OPEN ORDERS")
print("=" * 60)
try:
    orders = client.get_orders()
    if isinstance(orders, list):
        print(f"  Open orders: {len(orders)}")
        for o in orders:
            print(f"  {o.get('side','')} {o.get('original_size','')} @ {o.get('price','')} | filled: {o.get('size_matched','')} | status: {o.get('status','')}")
    else:
        print(f"  {orders}")
except Exception as e:
    print(f"  Error: {e}")

# 6. P&L Summary
print("\n" + "=" * 60)
print("P&L SUMMARY")
print("=" * 60)
starting_balance = 28.27
print(f"  Starting USDC.e: ${starting_balance:.2f}")
print(f"  Total spent on trades: ${total_spent:.4f}")
remaining = starting_balance - total_spent
print(f"  Remaining USDC.e (estimated): ${remaining:.4f}")
print(f"\n  Positions held:")
total_shares_value = 0
for asset_id, pos in positions.items():
    # Value at $1 if winning
    potential = pos['shares'] * 1.0
    print(f"    {pos['outcome']}: {pos['shares']:.2f} shares (cost ${pos['cost']:.4f}) → worth ${potential:.2f} IF wins")
    total_shares_value += potential

print(f"\n  Max potential value (if all win): ${total_shares_value:.2f}")
print(f"  But realistically only some will win")
print(f"  Net position: ${total_shares_value:.2f} potential - ${total_spent:.4f} spent")
