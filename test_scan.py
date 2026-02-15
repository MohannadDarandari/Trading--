"""Run scanners + test specific hedge token IDs against CLOB."""
import paramiko, textwrap

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("172.233.220.24", username="root", password="MOHANNAD@1011")

def run(cmd, timeout=180):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode(), stderr.read().decode()

# First read the rest of gamma_client _parse_market
print("=== _parse_market ===")
out, _ = run("grep -n '_parse_market\\|_parse_event' /root/polyclaw-bot/lib/gamma_client.py")
print(out)
out_l, _ = run("grep -n 'def _parse_market' /root/polyclaw-bot/lib/gamma_client.py | head -1 | cut -d: -f1")
lnum = int(out_l.strip()) if out_l.strip().isdigit() else 0
if lnum:
    out, _ = run(f"sed -n '{lnum},{lnum+30}p' /root/polyclaw-bot/lib/gamma_client.py")
    print(out)

# Write scanner test to VPS
test = textwrap.dedent("""
import asyncio, os, sys, json
os.chdir('/root/polyclaw-bot')
from dotenv import load_dotenv
load_dotenv()

from lib.gamma_client import GammaClient
from lib.clob_client import ClobClientWrapper

PK = '33b0c6d92c974489686742b4af56e168530a3f1d794a3c2c23831c59d8a369e9'
ADDR = '0xAdd5cf1e1d6992C0130C3a89094F300fA71d32E5'

async def main():
    gamma = GammaClient()
    clob = ClobClientWrapper(private_key=PK, address=ADDR)
    
    # Get events like EventGroupScanner does
    events = await gamma.get_events(limit=10)
    print(f"Got {len(events)} events")
    
    # Check token_ids from markets
    tested = 0
    for ev in events[:5]:
        for m in ev.markets[:3]:
            print(f"\\nMarket: {m.question[:50]}")
            print(f"  yes_token_id: {m.yes_token_id[:50]}..." if m.yes_token_id else "  yes_token_id: EMPTY")
            print(f"  no_token_id: {m.no_token_id[:50]}..." if m.no_token_id else "  no_token_id: EMPTY/None")
            print(f"  yes_price: {m.yes_price:.4f}, no_price: {m.no_price:.4f}")
            
            # Test order book for yes token
            if m.yes_token_id:
                try:
                    ob = clob.get_order_book(m.yes_token_id)
                    asks = ob.get('asks', [])
                    bids = ob.get('bids', [])
                    ask_depth = sum(float(a.get('price',0)) * float(a.get('size',0)) for a in asks)
                    print(f"  YES OB: {len(asks)} asks, {len(bids)} bids, depth=${ask_depth:.2f} ✅")
                except Exception as e:
                    print(f"  YES OB ERROR: {e}")
                tested += 1
            
            # Test order book for no token
            if m.no_token_id:
                try:
                    ob = clob.get_order_book(m.no_token_id)
                    asks = ob.get('asks', [])
                    bids = ob.get('bids', [])
                    ask_depth = sum(float(a.get('price',0)) * float(a.get('size',0)) for a in asks)
                    print(f"  NO OB:  {len(asks)} asks, {len(bids)} bids, depth=${ask_depth:.2f} ✅")
                except Exception as e:
                    print(f"  NO OB ERROR: {e}")
                tested += 1
            
            if tested >= 6:
                break
        if tested >= 6:
            break
    
    # Now try the specific hedge pattern: Fed Rates Decrease vs Increase
    print("\\n" + "="*50)
    print("TESTING KNOWN HEDGE PATTERNS")
    print("="*50)
    
    # Search for Fed rates markers
    all_events = await gamma.get_events(limit=50)
    for ev in all_events:
        if 'fed' in ev.title.lower() or 'rate' in ev.title.lower():
            print(f"\\nFed Event: {ev.title}")
            for m in ev.markets:
                print(f"  {m.question[:50]} | yes={m.yes_price:.3f} no={m.no_price:.3f}")
                print(f"    y_tid: {m.yes_token_id[:40]}..." if m.yes_token_id else "    y_tid: NONE")
                
                if m.yes_token_id:
                    try:
                        ob = clob.get_order_book(m.yes_token_id)
                        asks = ob.get('asks', [])
                        print(f"    YES OB: {len(asks)} asks ✅")
                    except Exception as e:
                        print(f"    YES OB: ERROR {e}")
    
    print("\\nDONE")

asyncio.run(main())
""")

run(f"cat > /tmp/test_scan.py << 'PYEOF'\n{test}\nPYEOF")
print("\n=== SCANNER + CLOB TEST ===")
out, err = run("cd /root/polyclaw-bot && /root/.local/bin/uv run python /tmp/test_scan.py 2>&1")
print(out)
if err:
    print("STDERR:", err[-500:])

ssh.close()
