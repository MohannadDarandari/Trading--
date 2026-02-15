"""Fix WARP: use --accept-tos on every command, chain in one session."""
import paramiko, time, textwrap

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("172.236.9.220", username="root", password="MOHANNAD@1011")

def run(cmd, timeout=60):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode(), stderr.read().decode()

# Chain all WARP commands with --accept-tos
print("=== WARP SETUP (chained) ===")
chain = """
warp-cli --accept-tos registration new 2>&1
echo "---REG DONE---"
warp-cli --accept-tos mode proxy 2>&1
echo "---MODE DONE---"
warp-cli --accept-tos connect 2>&1
echo "---CONNECT DONE---"
sleep 5
warp-cli --accept-tos status 2>&1
echo "---STATUS DONE---"
ss -tlnp | grep 40000 2>&1
echo "---PORT DONE---"
curl -s --socks5 127.0.0.1:40000 https://api.ipify.org 2>&1
echo "---WARP IP DONE---"
curl -s https://api.ipify.org 2>&1
echo "---DIRECT IP DONE---"
"""
out, err = run(chain, timeout=30)
print(out)

# Now test order through WARP proxy
print("\n=== ORDER TEST THROUGH WARP PROXY ===")
test = textwrap.dedent("""
import os, json, sys
os.chdir('/root/polyclaw-bot')

PK = '33b0c6d92c974489686742b4af56e168530a3f1d794a3c2c23831c59d8a369e9'
ADDR = '0xAdd5cf1e1d6992C0130C3a89094F300fA71d32E5'

# Set WARP proxy
os.environ['HTTPS_PROXY'] = 'socks5://127.0.0.1:40000'
os.environ['HTTP_PROXY'] = 'socks5://127.0.0.1:40000'

from py_clob_client.client import ClobClient
import requests as req

# check IP through proxy
try:
    s = req.Session()
    s.proxies = {'https': 'socks5://127.0.0.1:40000', 'http': 'socks5://127.0.0.1:40000'}
    r = s.get('https://api.ipify.org?format=json', timeout=10)
    print(f"Proxy IP: {r.json()}")
except Exception as e:
    print(f"Proxy IP check failed: {e}")
    print("WARP proxy not working, trying without proxy...")
    os.environ.pop('HTTPS_PROXY', None)
    os.environ.pop('HTTP_PROXY', None)

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

# Get real active market with orders
r = req.get("https://clob.polymarket.com/markets?next_cursor=MA==&limit=20")
markets = r.json()
if isinstance(markets, dict):
    markets = markets.get('data', [])

# Find an active market accepting orders
target = None
for m in markets:
    if m.get('active') and not m.get('closed') and m.get('accepting_orders'):
        tokens = m.get('tokens', [])
        if tokens:
            target = m
            break

if not target:
    print(f"No active market found. Markets: {json.dumps([{'q': m.get('question','')[:30], 'active': m.get('active'), 'closed': m.get('closed'), 'accepting': m.get('accepting_orders')} for m in markets[:5]])}")
    sys.exit(1)

print(f"Market: {target.get('question', '')[:80]}")
token_id = target['tokens'][0]['token_id']
print(f"Token: {token_id[:40]}...")

from py_clob_client.clob_types import OrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY

try:
    order = client.create_order(
        OrderArgs(
            token_id=token_id,
            price=0.01,
            size=1,
            side=BUY
        )
    )
    result = client.post_order(order, OrderType.GTC)
    print(f"ORDER RESULT: {json.dumps(result)}")
    oid = result.get('orderID', '')
    if oid:
        print(f"*** SUCCESS! Order placed: {oid} ***")
        cancel = client.cancel(oid)
        print(f"Cancelled: {cancel}")
except Exception as e:
    err = str(e)
    print(f"Order error: {err[:300]}")
    if '403' in err:
        print("STILL 403")
    else:
        print("Different error (not 403 = progress!)")
""")

run(f"cat > /tmp/test_warp_order.py << 'PYEOF'\n{test}\nPYEOF")
out, err = run("cd /root/polyclaw-bot && /root/.local/bin/uv run python /tmp/test_warp_order.py 2>&1", timeout=60)
print(out)
if err:
    print("STDERR:", err[-300:])

ssh.close()
