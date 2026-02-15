"""Connect WARP properly, test real order, restart bot."""
import paramiko, time, textwrap

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("172.236.9.220", username="root", password="MOHANNAD@1011")

def run(cmd, timeout=60):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode(), stderr.read().decode()

# 1. WARP status check and connect
print("=== WARP STATUS ===")
out, _ = run("warp-cli status 2>&1")
print(f"Status: {out.strip()}")

out, _ = run("warp-cli mode proxy 2>&1")
print(f"Mode proxy: {out.strip()}")

out, _ = run("warp-cli connect 2>&1")
print(f"Connect: {out.strip()}")

time.sleep(3)

out, _ = run("warp-cli status 2>&1")
print(f"Status after connect: {out.strip()}")

# Check if proxy port is listening
out, _ = run("ss -tlnp | grep 40000 2>&1")
print(f"Port 40000: {out.strip() or 'NOT LISTENING'}")

# Check IP through WARP proxy
out, _ = run("curl -s --socks5 127.0.0.1:40000 https://api.ipify.org 2>&1")
print(f"WARP IP: {out.strip()}")

# Also check direct IP
out, _ = run("curl -s https://api.ipify.org 2>&1")
print(f"Direct IP: {out.strip()}")

# 2. Test real order (WITHOUT proxy first, since 404 worked)
print("\n=== REAL ORDER TEST (no proxy) ===")
test = textwrap.dedent("""
import os, json, sys
os.chdir('/root/polyclaw-bot')

PK = '33b0c6d92c974489686742b4af56e168530a3f1d794a3c2c23831c59d8a369e9'
ADDR = '0xAdd5cf1e1d6992C0130C3a89094F300fA71d32E5'

for k in ['HTTPS_PROXY', 'HTTP_PROXY']:
    os.environ.pop(k, None)

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

# Get a real active market
import requests
r = requests.get("https://clob.polymarket.com/markets?next_cursor=MA==&limit=1")
markets = r.json()
if not markets:
    print("No markets!")
    sys.exit(1)

market = markets[0] if isinstance(markets, list) else markets.get('data', [markets])[0]
print(f"Market: {json.dumps(market)[:200]}")

tokens = market.get('tokens', [])
if not tokens:
    # Try another endpoint
    cid = market.get('condition_id', '')
    print(f"Condition ID: {cid}")
    r2 = requests.get(f"https://clob.polymarket.com/markets/{cid}")
    market = r2.json()
    tokens = market.get('tokens', [])
    print(f"Market detail: {json.dumps(market)[:200]}")

if tokens:
    token = tokens[0]
    token_id = token.get('token_id', '')
    print(f"Token ID: {token_id[:40]}...")
    
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
            print(f"SUCCESS! Order ID: {oid}")
            cancel = client.cancel(oid)
            print(f"Cancelled: {cancel}")
    except Exception as e:
        err = str(e)
        print(f"Order error: {err[:300]}")
        if '403' in err or 'regional' in err.lower():
            print("STILL GEO-BLOCKED!")
        elif '404' in err:
            print("404 = not geo-blocked, just bad market token")
else:
    print("No tokens found")
""")

run(f"cat > /tmp/test_real.py << 'PYEOF'\n{test}\nPYEOF")
out, err = run("cd /root/polyclaw-bot && /root/.local/bin/uv run python /tmp/test_real.py 2>&1", timeout=60)
print(out)
if err:
    print("STDERR:", err[-300:])

ssh.close()
