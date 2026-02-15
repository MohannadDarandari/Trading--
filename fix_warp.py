"""Fix: accept WARP TOS, regenerate API creds properly."""
import paramiko, time, textwrap

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("172.236.9.220", username="root", password="MOHANNAD@1011")

def run(cmd, timeout=120):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode(), stderr.read().decode()

# 1. Accept WARP TOS and setup
print("=== SETTING UP CLOUDFLARE WARP ===")
out, _ = run("warp-cli registration new --accept-tos 2>&1")
print(f"Register: {out.strip()}")

out, _ = run("warp-cli mode proxy 2>&1")
print(f"Mode: {out.strip()}")

out, _ = run("warp-cli connect 2>&1")
print(f"Connect: {out.strip()}")

time.sleep(5)

out, _ = run("warp-cli status 2>&1")
print(f"Status: {out.strip()}")

# Test WARP IP
out, _ = run("curl -x socks5://127.0.0.1:40000 -s http://ip-api.com/json 2>&1")
print(f"WARP IP: {out[:200]}")

# 2. Now test CLOB order through WARP proxy
print("\n=== TESTING CLOB VIA WARP ===")
test = textwrap.dedent("""
import os, json
os.chdir('/root/polyclaw-bot')

# Set proxy BEFORE imports
os.environ['HTTPS_PROXY'] = 'socks5://127.0.0.1:40000'
os.environ['HTTP_PROXY'] = 'socks5://127.0.0.1:40000'

PK = '33b0c6d92c974489686742b4af56e168530a3f1d794a3c2c23831c59d8a369e9'
ADDR = '0xAdd5cf1e1d6992C0130C3a89094F300fA71d32E5'

from py_clob_client.client import ClobClient
import py_clob_client.http_helpers.helpers as clob_helpers
import httpx

# Create client with WARP proxy
clob_helpers._http_client = httpx.Client(
    http2=True,
    proxy='socks5://127.0.0.1:40000',
    timeout=30.0
)

client = ClobClient(
    "https://clob.polymarket.com",
    key=PK,
    chain_id=137,
    signature_type=0,
    funder=ADDR,
)

creds = client.create_or_derive_api_creds()
client.set_api_creds(creds)
print(f"API creds set")

# Try placing a tiny order
from py_clob_client.clob_types import OrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY

try:
    order = client.create_order(
        OrderArgs(
            token_id='46531580883893457486521223946750972005651221984783428974972634868855238318041',
            price=0.01,
            size=1,
            side=BUY
        )
    )
    result = client.post_order(order, OrderType.GTC)
    print(f"ORDER PLACED! {json.dumps(result)[:200]}")
    oid = result.get('orderID', '')
    if oid:
        client.cancel(oid)
        print(f"Cancelled: {oid}")
except Exception as e:
    print(f"Order error: {e}")
    if '403' in str(e):
        print("Still blocked via WARP")
    elif 'connection' in str(e).lower() or 'proxy' in str(e).lower():
        print("WARP proxy connection issue")
""")

run(f"cat > /tmp/test_warp.py << 'PYEOF'\n{test}\nPYEOF")
out, err = run("cd /root/polyclaw-bot && /root/.local/bin/uv run python /tmp/test_warp.py 2>&1", timeout=60)
print(out)
if err:
    print("ERR:", err[-300:])

ssh.close()
