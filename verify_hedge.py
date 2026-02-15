"""Verify the Fed Rates hedge positions and expected payout."""
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

# Check open orders
print("=== OPEN ORDERS ===")
try:
    orders = client.get_orders()
    if isinstance(orders, list):
        print(f"Open orders: {len(orders)}")
        for o in orders:
            print(f"  {o.get('asset_id','')[:20]}... | {o.get('side','')} | size={o.get('original_size','')} @ {o.get('price','')} | status={o.get('status','')}")
    else:
        print(f"Orders response: {json.dumps(orders)[:200]}")
except Exception as e:
    print(f"Orders error: {e}")

# Check the markets for Fed Rates
print("\n=== FED RATES MARKETS ===")
for mid in ["654412", "654415"]:
    try:
        r = requests.get(f"https://gamma-api.polymarket.com/markets/{mid}")
        if r.ok:
            m = r.json()
            print(f"\nMarket {mid}: {m.get('question','')}")
            print(f"  Active: {m.get('active')}")
            print(f"  Closed: {m.get('closed')}")
            print(f"  Accepting orders: {m.get('acceptingOrders')}")
            
            # Check for group/condition
            cid = m.get('conditionId', '')
            gid = m.get('groupItemTitle', m.get('title', ''))
            eid = m.get('eventSlug', '')
            print(f"  Group: {gid}")
            print(f"  Event: {eid}")
            print(f"  Condition: {cid[:30]}...")
    except Exception as e:
        print(f"  Error: {e}")

# Check specific token order books
print("\n=== ORDER BOOKS ===")
tokens = {
    "Decrease": "46553455570564517989191023458705371521436514261892866503067981558938998232024",
    "Increase": "54073086346734626735797775941991553522163760164405051969883391401961188364109",
}
for name, tid in tokens.items():
    try:
        ob = client.get_order_book(tid)
        best_bid = ob.bids[0].price if ob.bids else "no bids"
        best_ask = ob.asks[0].price if ob.asks else "no asks"
        print(f"  {name}: bid={best_bid} | ask={best_ask}")
    except Exception as e:
        print(f"  {name}: {e}")

# My positions
print("\n=== MY POSITIONS ===")
try:
    # Try gamma positions endpoint
    r = requests.get(f"https://gamma-api.polymarket.com/positions?user={ADDR}&limit=20")
    positions = r.json()
    print(f"Positions: {json.dumps(positions)[:500]}")
except:
    pass

# Check trade history
print("\n=== RECENT TRADES ===")
try:
    trades = client.get_trades()
    if isinstance(trades, list):
        for t in trades[:5]:
            print(f"  {json.dumps(t)[:200]}")
    else:
        print(f"Trades: {json.dumps(trades)[:300]}")
except Exception as e:
    print(f"Trades error: {e}")

# Hedge profit calculation
print("\n=== HEDGE ANALYSIS ===")
leg1_price = 0.0065
leg2_price = 0.0055
shares = 181.82
total_cost = leg1_price * shares + leg2_price * shares
print(f"Total cost: ${total_cost:.4f}")
print(f"  Leg 1 (Decrease): {shares} shares @ ${leg1_price} = ${leg1_price * shares:.4f}")
print(f"  Leg 2 (Increase): {shares} shares @ ${leg2_price} = ${leg2_price * shares:.4f}")
print(f"If orders are GTC (limit) and at very low prices, they may not fill immediately")
print(f"If all fill: payout = ${shares:.2f} (winning side pays $1/share), profit = ${shares - total_cost:.2f}")
print(f"  This assumes Decrease + Increase covers ALL outcomes")
print(f"  If there's a 'No Change' option too, BOTH could lose!")
