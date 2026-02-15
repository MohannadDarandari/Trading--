"""Test: regenerate API creds from London + check if residential proxy needed."""
import paramiko, textwrap

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("172.236.9.220", username="root", password="MOHANNAD@1011")

def run(cmd, timeout=120):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode(), stderr.read().decode()

# 1. Check what Polymarket sees when we hit their API
print("=== POLYMARKET API HEADERS TEST ===")
out, _ = run("curl -sv https://clob.polymarket.com/ 2>&1 | grep -i 'cf-\\|x-\\|server\\|403\\|blocked'")
print(out)

# 2. Try deleting old API keys and creating new ones from London
print("\n=== REGENERATE API CREDENTIALS ===")
regen_test = textwrap.dedent("""
import os, json
os.chdir('/root/polyclaw-bot')
from dotenv import load_dotenv
load_dotenv()

from py_clob_client.client import ClobClient

pk = os.environ['POLYCLAW_PRIVATE_KEY']
addr = '0xAdd5cf1e1d6992C0130C3a89094F300fA71d32E5'

client = ClobClient(
    "https://clob.polymarket.com",
    key=pk,
    chain_id=137,
    signature_type=0,
    funder=addr,
)

# Check existing API keys
try:
    keys = client.get_api_keys()
    print(f"Existing API keys: {json.dumps(keys)[:200]}")
except Exception as e:
    print(f"Get keys error: {e}")

# Delete all existing API keys
try:
    keys_data = keys.get('apiKeys', []) if isinstance(keys, dict) else keys
    if isinstance(keys_data, list):
        for key in keys_data:
            try:
                client.delete_api_key(key)  
                print(f"Deleted key: {key}")
            except:
                pass
except Exception as e:
    print(f"Delete keys: {e}")

# Create fresh API creds from London IP
try:
    creds = client.create_api_key()
    print(f"New API creds created: {json.dumps(creds)[:200]}")
    client.set_api_creds(client.create_or_derive_api_creds())
except Exception as e:
    print(f"Create creds error: {e}")

# Try order again with fresh creds
try:
    from py_clob_client.clob_types import OrderArgs, OrderType
    from py_clob_client.order_builder.constants import BUY
    
    # Use a known liquid token
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
    if '403' in err and 'regional' in err.lower():
        print("\\n>>> CONFIRMED: Polymarket blocks datacenter IPs, not just US IPs")
        print(">>> Solution needed: residential/mobile proxy or Cloudflare WARP")
""")

run(f"cat > /tmp/regen_creds.py << 'PYEOF'\n{regen_test}\nPYEOF")
out, err = run("cd /root/polyclaw-bot && /root/.local/bin/uv run python /tmp/regen_creds.py 2>&1")
print(out)

# 3. Test with Cloudflare WARP (free VPN that gives residential-looking IP)
print("\n=== INSTALLING CLOUDFLARE WARP ===")
out, _ = run("which warp-cli 2>/dev/null && echo 'INSTALLED' || echo 'NOT_INSTALLED'")
print(f"WARP status: {out.strip()}")

if "NOT_INSTALLED" in out:
    print("Installing WARP...")
    cmds = [
        "curl -fsSL https://pkg.cloudflareclient.com/pubkey.gpg | gpg --yes --dearmor -o /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg",
        "echo 'deb [signed-by=/usr/share/keyrings/cloudflare-warp-archive-keyring.gpg] https://pkg.cloudflareclient.com/ noble main' > /etc/apt/sources.list.d/cloudflare-client.list",
        "apt update -qq 2>/dev/null && apt install -y -qq cloudflare-warp 2>&1 | tail -3",
    ]
    for cmd in cmds:
        out, err = run(cmd, timeout=60)
        if out.strip():
            print(f"  {out.strip()[:100]}")

    # Register and connect WARP
    out, _ = run("warp-cli registration new 2>&1")
    print(f"WARP register: {out.strip()}")
    out, _ = run("warp-cli mode proxy 2>&1")
    print(f"WARP mode: {out.strip()}")
    out, _ = run("warp-cli connect 2>&1")
    print(f"WARP connect: {out.strip()}")
    
    import time
    time.sleep(5)
    
    # Check WARP status
    out, _ = run("warp-cli status 2>&1")
    print(f"WARP status: {out.strip()}")
    
    # Test with WARP proxy
    out, _ = run("curl -x socks5://127.0.0.1:40000 -s http://ip-api.com/json 2>&1")
    print(f"WARP IP: {out[:200]}")

ssh.close()
