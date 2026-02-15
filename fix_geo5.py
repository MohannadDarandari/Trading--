"""Install pysocks, find active market, test order through WARP."""
import paramiko, time, textwrap

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("172.236.9.220", username="root", password="MOHANNAD@1011")

def run(cmd, timeout=120):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode(), stderr.read().decode()

# 1. Install pysocks
print("=== INSTALL PYSOCKS ===")
out, _ = run("cd /root/polyclaw-bot && /root/.local/bin/uv pip install pysocks 2>&1")
print(out.strip()[:200])

# 2. Verify WARP still connected
out, _ = run("warp-cli --accept-tos status 2>&1")
print(f"\nWARP: {out.strip()}")

# 3. Test order through WARP
test = textwrap.dedent("""
import os, json, sys
os.chdir('/root/polyclaw-bot')

PK = '33b0c6d92c974489686742b4af56e168530a3f1d794a3c2c23831c59d8a369e9'
ADDR = '0xAdd5cf1e1d6992C0130C3a89094F300fA71d32E5'

# Set WARP SOCKS5 proxy  
os.environ['HTTPS_PROXY'] = 'socks5h://127.0.0.1:40000'
os.environ['HTTP_PROXY'] = 'socks5h://127.0.0.1:40000'

import requests as req

# Verify proxy IP
try:
    r = req.get('https://api.ipify.org?format=json', timeout=10)
    ip = r.json()['ip']
    print(f"Request IP via proxy: {ip}")
    r2 = req.get(f'http://ip-api.com/json/{ip}', timeout=10)
    info = r2.json()
    print(f"IP info: {info.get('country')} | {info.get('isp')} | {info.get('org')}")
except Exception as e:
    print(f"Proxy IP check: {e}")

from py_clob_client.client import ClobClient

# The ClobClient uses httpx internally, which reads HTTPS_PROXY
client = ClobClient(
    "https://clob.polymarket.com",
    key=PK,
    chain_id=137,
    signature_type=0,
    funder=ADDR,
)

creds = client.create_or_derive_api_creds()
client.set_api_creds(creds)
print(f"Creds: {creds.api_key[:15]}...")

# Get sampling endpoint for active markets
r = req.get("https://clob.polymarket.com/sampling-markets?next_cursor=MA==&limit=10")
data = r.json()
print(f"Sampling: {json.dumps(data)[:300]}")

# Also try gamma API for active markets
r = req.get("https://gamma-api.polymarket.com/markets?closed=false&active=true&limit=5")
gamma = r.json()
print(f"\\nGamma markets: {len(gamma)}")

if gamma:
    for gm in gamma[:3]:
        cid = gm.get('conditionId') or gm.get('condition_id', '')
        q = gm.get('question', '')[:60]
        print(f"  {q} | cid={cid[:20]}...")

# Try CLOB markets endpoint with different params
r = req.get("https://clob.polymarket.com/markets?limit=50")
clob_data = r.json()
if isinstance(clob_data, dict):
    all_markets = clob_data.get('data', [])
else:
    all_markets = clob_data

active = [m for m in all_markets if m.get('active') and not m.get('closed') and m.get('accepting_orders')]
print(f"\\nActive accepting orders: {len(active)} / {len(all_markets)}")

if active:
    m = active[0]
    print(f"Using: {m.get('question', '')[:80]}")
    token_id = m['tokens'][0]['token_id']
    print(f"Token: {token_id[:40]}...")
    
    from py_clob_client.clob_types import OrderArgs, OrderType
    from py_clob_client.order_builder.constants import BUY
    
    try:
        order = client.create_order(
            OrderArgs(
                token_id=token_id,
                price=0.01,
                size=max(float(m.get('minimum_order_size', 5)), 5),
                side=BUY
            )
        )
        result = client.post_order(order, OrderType.GTC)
        print(f"\\n*** ORDER RESULT: {json.dumps(result)} ***")
        oid = result.get('orderID', '')
        if oid:
            print(f"SUCCESS! Order ID: {oid}")
            cancel = client.cancel(oid)
            print(f"Cancelled: {cancel}")
    except Exception as e:
        err = str(e)
        print(f"\\nOrder error: {err[:400]}")
        if '403' in err and 'regional' in err.lower():
            print(">>> STILL GEO-BLOCKED EVEN THROUGH WARP <<<")
        elif '403' in err:
            print(">>> 403 but not regional <<<")
        else:
            print(f">>> Different error (not 403) <<<")
else:
    # Try with first gamma market's token
    if gamma:
        gm = gamma[0]
        cid = gm.get('conditionId', '')
        if cid:
            print(f"\\nTrying gamma market cid: {cid}")
            r = req.get(f"https://clob.polymarket.com/markets/{cid}")
            cm = r.json()
            tokens = cm.get('tokens', [])
            if tokens:
                token_id = tokens[0]['token_id']
                print(f"Token: {token_id[:40]}...")
                
                from py_clob_client.clob_types import OrderArgs, OrderType
                from py_clob_client.order_builder.constants import BUY
                
                try:
                    order = client.create_order(
                        OrderArgs(
                            token_id=token_id,
                            price=0.01,
                            size=max(float(cm.get('minimum_order_size', 5)), 5),
                            side=BUY
                        )
                    )
                    result = client.post_order(order, OrderType.GTC)
                    print(f"\\n*** ORDER RESULT: {json.dumps(result)} ***")
                    oid = result.get('orderID', '')
                    if oid:
                        print(f"SUCCESS!")
                        client.cancel(oid)
                except Exception as e:
                    print(f"Order error: {str(e)[:400]}")
""")

run(f"cat > /tmp/test_warp2.py << 'PYEOF'\n{test}\nPYEOF")
out, err = run("cd /root/polyclaw-bot && /root/.local/bin/uv run python /tmp/test_warp2.py 2>&1", timeout=60)
print("\n=== ORDER TEST ===")
print(out)
if err:
    print("STDERR:", err[-300:])

ssh.close()
