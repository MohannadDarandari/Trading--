"""Test CLOB API calls directly on VPS to see what errors occur."""
import paramiko, textwrap

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("172.233.220.24", username="root", password="MOHANNAD@1011")

def run(cmd, timeout=120):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode(), stderr.read().decode()

# 1. Check full_scan code around line 1320-1340 to see kill message + exec decision
print("=== FULL SCAN CODE 1310-1410 ===")
out, _ = run("sed -n '1310,1410p' /root/polyclaw-bot/hedge_server_v4.py")
print(out)

# 2. Test CLOB directly on VPS
test_script = textwrap.dedent(r"""
import os, json, sys
os.chdir('/root/polyclaw-bot')

# Load env
from dotenv import load_dotenv
load_dotenv()

pk = os.environ.get('POLYCLAW_PRIVATE_KEY', '')
addr = '0xAdd5cf1e1d6992C0130C3a89094F300fA71d32E5'
print(f"PK loaded: {bool(pk)} ({pk[:8]}...)")

# Init CLOB client
from lib.clob_client import ClobClientWrapper
clob = ClobClientWrapper(private_key=pk, address=addr)
print("CLOB wrapper created")

# Try to init client
try:
    c = clob.client
    print(f"CLOB client initialized: {type(c)}")
except Exception as e:
    print(f"CLOB init FAILED: {e}")
    sys.exit(1)

# Try get_order_book for a known market
# Bitcoin > $100k market: 0x... (let's use the API to find one)
try:
    # Get active markets first
    markets = c.get_markets()
    print(f"Got {len(markets)} markets from API")
    if markets:
        # Find one with a token_id
        for m in markets[:5]:
            tid = m.get('tokens', [{}])[0].get('token_id', '')
            if tid:
                print(f"\nTesting order book for: {m.get('question', '')[:60]}")
                print(f"Token ID: {tid[:30]}...")
                ob = clob.get_order_book(tid)
                asks = ob.get('asks', [])
                bids = ob.get('bids', [])
                print(f"Asks: {len(asks)}, Bids: {len(bids)}")
                if asks:
                    print(f"Best ask: ${asks[0]}")
                break
except Exception as e:
    print(f"Market/OrderBook error: {e}")
    import traceback
    traceback.print_exc()

# Check API key/creds
try:
    api_keys = c.get_api_keys()
    print(f"\nAPI keys: {len(api_keys)} keys registered")
except Exception as e:
    print(f"\nAPI keys check error: {e}")

print("\nDONE")
""")

# Write and run the test
run(f"cat > /tmp/test_clob.py << 'PYEOF'\n{test_script}\nPYEOF")
print("\n=== CLOB TEST OUTPUT ===")
out, err = run("cd /root/polyclaw-bot && /root/.local/bin/uv run python /tmp/test_clob.py 2>&1")
print(out)
if err:
    print("STDERR:", err[-500:])

ssh.close()
