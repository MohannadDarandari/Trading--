"""Fix WARP + test fresh API creds from London."""
import paramiko, time, textwrap

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("172.236.9.220", username="root", password="MOHANNAD@1011")

def run(cmd, timeout=120):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode(), stderr.read().decode()

# 1. Try WARP with correct TOS acceptance
print("=== WARP SETUP ===")
# Try various ways to accept TOS
for cmd in [
    "yes | warp-cli registration new 2>&1",
    "warp-cli --accept-tos registration new 2>&1", 
    "echo 'yes' | warp-cli registration new 2>&1",
]:
    out, _ = run(cmd)
    print(f"  {cmd[:40]}: {out.strip()[:100]}")
    if "Success" in out or "already" in out.lower():
        break

# Check WARP help
out, _ = run("warp-cli registration new --help 2>&1")
print(f"\nWARP help: {out[:300]}")

# 2. Try without WARP — fresh API key from London (no proxy)
print("\n=== FRESH API CREDS TEST (no proxy) ===")
test = textwrap.dedent("""
import os, json, sys
os.chdir('/root/polyclaw-bot')

PK = '33b0c6d92c974489686742b4af56e168530a3f1d794a3c2c23831c59d8a369e9'
ADDR = '0xAdd5cf1e1d6992C0130C3a89094F300fA71d32E5'

# Make sure NO proxy is set  
for k in ['HTTPS_PROXY', 'HTTP_PROXY', 'https_proxy', 'http_proxy']:
    os.environ.pop(k, None)

from py_clob_client.client import ClobClient

client = ClobClient(
    "https://clob.polymarket.com",
    key=PK,
    chain_id=137,
    signature_type=0,
    funder=ADDR,
)

# 1. Get existing API keys
try:
    # Derive creds first to authenticate
    creds = client.create_or_derive_api_creds()
    client.set_api_creds(creds)
    print(f"Creds OK: key={creds.api_key[:15]}...")
except Exception as e:
    print(f"Creds error: {e}")
    sys.exit(1)

# 2. Try to get API keys list  
try:
    keys = client.get_api_keys()
    print(f"API keys: {json.dumps(keys)[:200]}")
except Exception as e:
    print(f"API keys error: {e}")

# 3. Try to delete all API keys and re-create
try:
    client.delete_api_key()
    print("Deleted old API key")
except Exception as e:
    print(f"Delete error: {e}")

# 4. Create completely new API key
try:
    new_creds = client.create_api_key()
    print(f"New API key: {json.dumps(new_creds)[:200]}")
    client.set_api_creds(client.create_or_derive_api_creds())
except Exception as e:
    print(f"Create new key error: {e}")

# 5. Try order with new creds
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
    print(f"ORDER SUCCESS: {json.dumps(result)[:200]}")
    oid = result.get('orderID', '')
    if oid:
        client.cancel(oid)
        print(f"Cancelled: {oid}")
except Exception as e:
    err = str(e)
    print(f"Order error: {err}")
    if 'regional' in err.lower():
        # Check what IP Polymarket sees
        import requests
        r = requests.get('https://api.ipify.org?format=json')
        print(f"My IP: {r.json()}")
        r2 = requests.get(f'http://ip-api.com/json/{r.json()["ip"]}')
        info = r2.json()
        print(f"IP info: {info.get('country')} / {info.get('isp')} / {info.get('org')}")
        print(f"AS: {info.get('as')}")
""")

run(f"cat > /tmp/test_fresh.py << 'PYEOF'\n{test}\nPYEOF")
out, err = run("cd /root/polyclaw-bot && /root/.local/bin/uv run python /tmp/test_fresh.py 2>&1", timeout=60)
print(out)
if err:
    print("ERR:", err[-200:])

ssh.close()
