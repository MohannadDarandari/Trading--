"""Check if orderbook fix works + get detailed execution debug logs."""
import paramiko, time, textwrap

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("172.233.220.24", username="root", password="MOHANNAD@1011")

def run(cmd, timeout=120):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode(), stderr.read().decode()

# 1. Verify the fix in clob_client.py
print("=== CURRENT clob_client.py get_order_book ===")
out, _ = run("grep -A3 'def get_order_book' /root/polyclaw-bot/lib/clob_client.py")
print(out)

# 2. Test fix directly
test = textwrap.dedent("""
import asyncio, os
os.chdir('/root/polyclaw-bot')
from dotenv import load_dotenv
load_dotenv()

from lib.gamma_client import GammaClient
from lib.clob_client import ClobClientWrapper

async def main():
    gamma = GammaClient()
    clob = ClobClientWrapper(
        private_key='33b0c6d92c974489686742b4af56e168530a3f1d794a3c2c23831c59d8a369e9',
        address='0xAdd5cf1e1d6992C0130C3a89094F300fA71d32E5'
    )
    
    # Get a real token_id from gamma
    events = await gamma.get_events(limit=5)
    for ev in events:
        for m in ev.markets[:2]:
            if m.yes_token_id and m.active and not m.closed:
                tid = m.yes_token_id
                print(f"Testing: {m.question[:50]}")
                print(f"Token: {tid[:40]}...")
                try:
                    ob = clob.get_order_book(tid)
                    print(f"Type: {type(ob)}")
                    print(f"Has .get: {hasattr(ob, 'get')}")
                    asks = ob.get('asks', [])
                    bids = ob.get('bids', [])
                    print(f"Asks: {len(asks)}, Bids: {len(bids)}")
                    if asks:
                        a = asks[0]
                        print(f"First ask: price={a.get('price')}, size={a.get('size')}")
                        print(f"Float test: {float(a.get('price', 0))}")
                    print("ORDER BOOK FIX WORKS!")
                    return
                except Exception as e:
                    print(f"ERROR: {e}")
                    import traceback
                    traceback.print_exc()
                    return
    print("No testable market found")

asyncio.run(main())
""")

run(f"cat > /tmp/test_ob_fix.py << 'PYEOF'\n{test}\nPYEOF")
out, err = run("cd /root/polyclaw-bot && /root/.local/bin/uv run python /tmp/test_ob_fix.py 2>&1")
print("\n=== ORDER BOOK FIX TEST ===")
print(out)
if err:
    print("ERR:", err[-300:])

# 3. Check DB for any new records (orders, incidents, depth_checks)
print("\n=== DB STATUS ===")
db_test = textwrap.dedent("""
import sqlite3
conn = sqlite3.connect('/root/polyclaw-bot/data/hedge_bot.db')
cur = conn.cursor()
for table in ['orders', 'incidents', 'depth_checks', 'pnl']:
    cur.execute(f'SELECT COUNT(*) FROM {table}')
    cnt = cur.fetchone()[0]
    print(f'{table}: {cnt} rows')
    if cnt > 0:
        cur.execute(f'SELECT * FROM {table} ORDER BY id DESC LIMIT 3')
        cols = [d[0] for d in cur.description]
        print(f'  Columns: {cols}')
        for row in cur.fetchall():
            print(f'  {row}')
""")
run(f"cat > /tmp/check_db.py << 'PYEOF'\n{db_test}\nPYEOF")
out, _ = run("cd /root/polyclaw-bot && /root/.local/bin/uv run python /tmp/check_db.py 2>&1")
print(out)

# 4. Check full journal with stderr
print("\n=== FULL JOURNAL (last 2 min) ===")
out, _ = run("journalctl -u polyclaw-bot --since '2 min ago' --no-pager --output=cat 2>&1")
print(out)

ssh.close()
