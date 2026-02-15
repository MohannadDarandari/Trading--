"""Test CLOB with explicit key + check how bot loads key + verify .env."""
import paramiko, textwrap

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("172.233.220.24", username="root", password="MOHANNAD@1011")

def run(cmd, timeout=120):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode(), stderr.read().decode()

# 1. Check .env contents
print("=== .ENV FILE ===")
out, _ = run("cat /root/polyclaw-bot/.env")
print(out)

# 2. How bot loads the key (around line 1100-1120)
print("=== BOT KEY LOADING ===")
out, _ = run("sed -n '1080,1130p' /root/polyclaw-bot/hedge_server_v4.py")
print(out)

# 3. Test CLOB with explicit key
test_script = textwrap.dedent("""
import os, sys, json
os.chdir('/root/polyclaw-bot')

pk = '33b0c6d92c974489686742b4af56e168530a3f1d794a3c2c23831c59d8a369e9'
addr = '0xAdd5cf1e1d6992C0130C3a89094F300fA71d32E5'

from lib.clob_client import ClobClientWrapper
clob = ClobClientWrapper(private_key=pk, address=addr)

# Force init
try:
    c = clob.client
    print(f"CLOB client OK: {type(c).__name__}")
except Exception as e:
    print(f"CLOB init FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Try API keys
try:
    keys = c.get_api_keys()
    print(f"API keys: {json.dumps(keys)[:200]}")
except Exception as e:
    print(f"API keys error: {e}")

# Try get markets  
try:
    import requests
    resp = requests.get('https://gamma-api.polymarket.com/markets?limit=3&active=true')
    markets = resp.json()
    print(f"Gamma API: {len(markets)} markets")
    for m in markets:
        tokens = m.get('clobTokenIds', '').split(',') if m.get('clobTokenIds') else []
        if tokens and tokens[0]:
            tid = tokens[0].strip()
            print(f"  Testing order book for token: {tid[:40]}...")
            try:
                ob = clob.get_order_book(tid)
                asks = ob.get('asks', [])
                bids = ob.get('bids', [])
                print(f"  Result: {len(asks)} asks, {len(bids)} bids")
                if asks:
                    print(f"  Best ask: {asks[0]}")
                break
            except Exception as e:
                print(f"  OB error: {e}")
except Exception as e:
    print(f"Market test error: {e}")
    import traceback
    traceback.print_exc()

# Try a tiny buy order (DRY RUN - create but don't post)
try:
    from py_clob_client.clob_types import OrderArgs, OrderType
    from py_clob_client.order_builder.constants import BUY
    
    # Get a real token_id from gamma API
    resp = requests.get('https://gamma-api.polymarket.com/markets?limit=10&active=true&closed=false')
    markets = resp.json()
    test_tid = None
    for m in markets:
        tids = m.get('clobTokenIds', '').split(',')
        if tids and tids[0].strip():
            test_tid = tids[0].strip()
            q = m.get('question', '')[:60]
            break
    
    if test_tid:
        print(f"\\nTest order for: {q}")
        print(f"Token: {test_tid[:40]}...")
        # Create order (signed, but don't post it to check auth works)
        order = c.create_order(
            OrderArgs(token_id=test_tid, price=0.01, size=1, side=BUY)
        )
        print(f"Order created (signed): {json.dumps(order)[:200]}")
        
        # Now actually try posting a tiny $0.01 order
        try:
            result = c.post_order(order, OrderType.GTC)
            print(f"Order posted! Result: {json.dumps(result)[:200]}")
            # Cancel it immediately
            oid = result.get('orderID', '')
            if oid:
                c.cancel(oid)
                print(f"Cancelled order {oid}")
        except Exception as e:
            print(f"Post order error: {e}")
    else:
        print("No test market found")
        
except Exception as e:
    print(f"Order test error: {e}")
    import traceback
    traceback.print_exc()

print("\\nDONE")
""")

run(f"cat > /tmp/test_clob2.py << 'PYEOF'\n{test_script}\nPYEOF")
print("\n=== CLOB TEST WITH EXPLICIT KEY ===")
out, err = run("cd /root/polyclaw-bot && /root/.local/bin/uv run python /tmp/test_clob2.py 2>&1")
print(out)
if err:
    print("STDERR:", err[-500:])

ssh.close()
