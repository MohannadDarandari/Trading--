"""Check what token_ids the scanners produce and test them against CLOB."""
import paramiko, textwrap

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("172.233.220.24", username="root", password="MOHANNAD@1011")

def run(cmd, timeout=120):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode(), stderr.read().decode()

# 1. Read the Gamma client to see how Market parses token_ids
print("=== GAMMA CLIENT ===")
out, _ = run("cat /root/polyclaw-bot/lib/gamma_client.py")
print(out[:5000])

# 2. Also check Market/MarketGroup class
print("=== MARKET CLASS IN V4 ===")
out, _ = run("grep -n 'class Market\\|yes_token_id\\|no_token_id\\|clobTokenIds\\|token_id' /root/polyclaw-bot/hedge_server_v4.py | head -25")
print(out)

# Get Market class definition
out_l, _ = run("grep -n 'class Market' /root/polyclaw-bot/hedge_server_v4.py | head -1 | cut -d: -f1")
lnum = int(out_l.strip()) if out_l.strip().isdigit() else 0
if lnum:
    print(f"\n=== Market class at line {lnum} ===")
    out, _ = run(f"sed -n '{lnum},{lnum+40}p' /root/polyclaw-bot/hedge_server_v4.py")
    print(out)

# 3. Run scanner simulation
test = textwrap.dedent("""
import os, sys, json
os.chdir('/root/polyclaw-bot')
from dotenv import load_dotenv
load_dotenv()
os.environ['POLYCLAW_PRIVATE_KEY'] = '33b0c6d92c974489686742b4af56e168530a3f1d794a3c2c23831c59d8a369e9'

# Import the gamma client
from lib.gamma_client import GammaClient
gamma = GammaClient()

# Get some events
events = gamma.get_events(limit=10, active=True)
print(f"Got {len(events)} events")

for ev in events[:3]:
    print(f"\\nEvent: {ev.get('title', '')[:60]}")
    markets = ev.get('markets', [])
    for m in markets[:3]:
        q = m.get('question', '')[:50]
        yes_tid = m.get('clobTokenIds', '')
        print(f"  Q: {q}")
        print(f"  clobTokenIds raw: {yes_tid[:100]}")
        
        # Parse like the bot does
        tokens = m.get('clobTokenIds', '').split(',') if isinstance(m.get('clobTokenIds'), str) else m.get('clobTokenIds', [])
        for i, t in enumerate(tokens):
            t = t.strip().strip('[]"')
            print(f"  Token[{i}]: {t[:60]}...")

# Now test with the CLOB client
from lib.clob_client import ClobClientWrapper
clob = ClobClientWrapper(
    private_key='33b0c6d92c974489686742b4af56e168530a3f1d794a3c2c23831c59d8a369e9',
    address='0xAdd5cf1e1d6992C0130C3a89094F300fA71d32E5'
)

# Get a valid token from gamma
for ev in events[:5]:
    for m in ev.get('markets', []):
        raw = m.get('clobTokenIds', '')
        try:
            tids = json.loads(raw) if isinstance(raw, str) else raw
        except:
            tids = []
        for tid in (tids if isinstance(tids, list) else []):
            tid = str(tid).strip()
            if tid and len(tid) > 10:
                print(f"\\nTesting CLOB for: {m.get('question', '')[:40]}")
                print(f"Token: {tid[:50]}...")
                try:
                    ob = clob.get_order_book(tid)
                    asks = ob.get('asks', [])
                    bids = ob.get('bids', [])
                    print(f"  -> {len(asks)} asks, {len(bids)} bids ✅")
                    if asks:
                        print(f"  Best ask: {asks[0]}")
                    break
                except Exception as e:
                    print(f"  -> ERROR: {e}")
        else:
            continue
        break

print("\\nDONE")
""")

run(f"cat > /tmp/test_tokens.py << 'PYEOF'\n{test}\nPYEOF")
print("\n=== TOKEN TEST OUTPUT ===")
out, err = run("cd /root/polyclaw-bot && /root/.local/bin/uv run python /tmp/test_tokens.py 2>&1")
print(out)
if err:
    print("STDERR:", err[-500:])

ssh.close()
