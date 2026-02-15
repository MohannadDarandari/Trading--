"""Test order from local machine (residential IP)."""
import os, json, sys

PK = '33b0c6d92c974489686742b4af56e168530a3f1d794a3c2c23831c59d8a369e9'
ADDR = '0xAdd5cf1e1d6992C0130C3a89094F300fA71d32E5'

# Clear any proxy
for k in ['HTTPS_PROXY', 'HTTP_PROXY', 'https_proxy', 'http_proxy']:
    os.environ.pop(k, None)

import requests as req

# Check our IP
r = req.get('https://api.ipify.org?format=json', timeout=10)
ip = r.json()['ip']
print(f"Local IP: {ip}")
r2 = req.get(f'http://ip-api.com/json/{ip}', timeout=10)
info = r2.json()
print(f"IP info: {info.get('country')} | {info.get('isp')} | {info.get('org')}")
print(f"Type: {'residential' if 'hosting' not in info.get('org','').lower() and 'cloud' not in info.get('org','').lower() else 'datacenter'}")

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
print(f"\nCreds: {creds.api_key[:15]}...")

# Find active market via gamma API
r = req.get("https://gamma-api.polymarket.com/markets?closed=false&active=true&limit=5")
gamma = r.json()

for gm in gamma:
    cid = gm.get('conditionId', '')
    if not cid:
        continue
    
    # Get CLOB market details
    r = req.get(f"https://clob.polymarket.com/markets/{cid}")
    cm = r.json()
    
    if cm.get('accepting_orders') and cm.get('tokens'):
        q = cm.get('question', gm.get('question', ''))[:80]
        token_id = cm['tokens'][0]['token_id']
        min_size = max(float(cm.get('minimum_order_size', 5)), 5)
        print(f"\nMarket: {q}")
        print(f"Token: {token_id[:40]}...")
        print(f"Min size: {min_size}")
        
        from py_clob_client.clob_types import OrderArgs, OrderType
        from py_clob_client.order_builder.constants import BUY
        
        try:
            order = client.create_order(
                OrderArgs(
                    token_id=token_id,
                    price=0.01,
                    size=min_size,
                    side=BUY
                )
            )
            result = client.post_order(order, OrderType.GTC)
            print(f"\n*** ORDER RESULT: {json.dumps(result)} ***")
            oid = result.get('orderID', '')
            if oid:
                print(f"SUCCESS! Order placed from residential IP: {oid}")
                cancel = client.cancel(oid)
                print(f"Cancelled: {cancel}")
        except Exception as e:
            err = str(e)
            print(f"\nOrder error: {err[:400]}")
            if '403' in err and 'regional' in err.lower():
                print(">>> GEO-BLOCKED even from residential IP <<<")
            elif '403' in err:
                print(">>> 403 but not regional <<<")
            else:
                print(f">>> Error type: {type(e).__name__} <<<")
        break
else:
    print("No active market found accepting orders")
