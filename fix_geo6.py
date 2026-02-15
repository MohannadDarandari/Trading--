"""Try WARP full tunnel mode on VPS + test order."""
import paramiko, time, textwrap

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("172.236.9.220", username="root", password="MOHANNAD@1011")

def run(cmd, timeout=60):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode(), stderr.read().decode()

# 1. Switch WARP to full tunnel mode (warp mode instead of proxy)
print("=== SWITCH WARP TO FULL TUNNEL ===")
out, _ = run("warp-cli --accept-tos disconnect 2>&1")
print(f"Disconnect: {out.strip()}")

out, _ = run("warp-cli --accept-tos mode warp 2>&1")
print(f"Mode warp: {out.strip()}")

out, _ = run("warp-cli --accept-tos connect 2>&1")
print(f"Connect: {out.strip()}")

time.sleep(5)

out, _ = run("warp-cli --accept-tos status 2>&1")
print(f"Status: {out.strip()}")

# Check IP through full tunnel
out, _ = run("curl -s https://api.ipify.org 2>&1")
print(f"IP via WARP tunnel: {out.strip()}")

out, _ = run(f"curl -s http://ip-api.com/json/{out.strip()} 2>&1")
print(f"IP info: {out.strip()[:200]}")

# 2. Test order through full WARP tunnel (no proxy needed - all traffic goes through WARP)
print("\n=== ORDER TEST (full WARP tunnel) ===")
test = textwrap.dedent("""
import os, json, sys
os.chdir('/root/polyclaw-bot')

PK = '33b0c6d92c974489686742b4af56e168530a3f1d794a3c2c23831c59d8a369e9'
ADDR = '0xAdd5cf1e1d6992C0130C3a89094F300fA71d32E5'

# NO proxy needed - full tunnel mode routes everything through WARP
for k in ['HTTPS_PROXY', 'HTTP_PROXY', 'https_proxy', 'http_proxy']:
    os.environ.pop(k, None)

import requests as req

# Check IP
r = req.get('https://api.ipify.org?format=json', timeout=10)
ip = r.json()['ip']
print(f"Python IP: {ip}")
r2 = req.get(f'http://ip-api.com/json/{ip}', timeout=10)
info = r2.json()
print(f"IP info: {info.get('country')} | {info.get('isp')} | {info.get('org')}")

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
print(f"Creds: {creds.api_key[:15]}...")

# Find active market
r = req.get("https://gamma-api.polymarket.com/markets?closed=false&active=true&limit=5")
gamma = r.json()

for gm in gamma:
    cid = gm.get('conditionId', '')
    if not cid:
        continue
    r = req.get(f"https://clob.polymarket.com/markets/{cid}")
    cm = r.json()
    if cm.get('accepting_orders') and cm.get('tokens'):
        token_id = cm['tokens'][0]['token_id']
        min_size = max(float(cm.get('minimum_order_size', 5)), 5)
        q = cm.get('question', '')[:80]
        print(f"\\nMarket: {q}")
        
        from py_clob_client.clob_types import OrderArgs, OrderType
        from py_clob_client.order_builder.constants import BUY
        
        try:
            order = client.create_order(
                OrderArgs(token_id=token_id, price=0.01, size=min_size, side=BUY)
            )
            result = client.post_order(order, OrderType.GTC)
            print(f"ORDER RESULT: {json.dumps(result)}")
            oid = result.get('orderID', '')
            if oid:
                print(f"*** SUCCESS from VPS WARP! ***")
                client.cancel(oid)
        except Exception as e:
            err = str(e)
            print(f"Order error: {err[:300]}")
            if '403' in err:
                print("STILL BLOCKED")
        break
""")

run(f"cat > /tmp/test_warp_full.py << 'PYEOF'\n{test}\nPYEOF")
out, err = run("cd /root/polyclaw-bot && /root/.local/bin/uv run python /tmp/test_warp_full.py 2>&1", timeout=60)
print(out)

# 3. If still blocked, switch back to proxy mode for other use
print("\n=== SWITCHING BACK TO PROXY MODE ===")
out, _ = run("warp-cli --accept-tos disconnect 2>&1")
out, _ = run("warp-cli --accept-tos mode proxy 2>&1")
out, _ = run("warp-cli --accept-tos connect 2>&1")
print(f"Proxy mode restored: {out.strip()}")

ssh.close()
