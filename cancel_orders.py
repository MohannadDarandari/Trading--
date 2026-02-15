"""Cancel any open orders from the partial fills."""
import os
os.chdir(r"C:\Users\mdara\OneDrive\Desktop\DarkOps HQ\Trading$$")

from dotenv import load_dotenv
load_dotenv()

PK = os.environ['POLYCLAW_PRIVATE_KEY']
ADDR = '0xAdd5cf1e1d6992C0130C3a89094F300fA71d32E5'

from py_clob_client.client import ClobClient

client = ClobClient(
    "https://clob.polymarket.com",
    key=PK,
    chain_id=137,
    signature_type=0,
    funder=ADDR,
)
creds = client.create_or_derive_api_creds()
client.set_api_creds(creds)

# Get open orders
try:
    open_orders = client.get_orders()
    print(f"Open orders: {len(open_orders) if isinstance(open_orders, list) else open_orders}")
    
    if isinstance(open_orders, list) and open_orders:
        for o in open_orders:
            oid = o.get('id', o.get('orderID', ''))
            print(f"  Cancelling: {oid[:20]}... | {o.get('side', '')} @ {o.get('price', '')} x{o.get('size', '')}")
        
        # Cancel all
        result = client.cancel_all()
        print(f"Cancel all result: {result}")
    elif isinstance(open_orders, dict):
        orders = open_orders.get('data', [])
        print(f"  Found {len(orders)} orders")
        if orders:
            result = client.cancel_all()
            print(f"Cancel all: {result}")
except Exception as e:
    print(f"Error: {e}")
    # Try cancel_all directly
    try:
        result = client.cancel_all()
        print(f"Cancel all: {result}")
    except Exception as e2:
        print(f"Cancel all error: {e2}")

print("\nDone!")
