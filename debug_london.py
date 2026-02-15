"""Deep debug London VPS: check why execute_hedge not producing orders."""
import paramiko, textwrap

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("172.236.9.220", username="root", password="MOHANNAD@1011")

def run(cmd, timeout=120):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode(), stderr.read().decode()

# 1. Verify the code has our fixes
print("=== CODE VERIFICATION ===")
out, _ = run("grep 'TRADE_BUDGET' /root/polyclaw-bot/hedge_server_v4.py | head -3")
print(f"TRADE_BUDGET: {out.strip()}")
out, _ = run("grep 'KILL_API_ERRORS' /root/polyclaw-bot/hedge_server_v4.py | head -1")
print(f"KILL_API: {out.strip()}")
out, _ = run("grep 'AUTO_TRADE' /root/polyclaw-bot/hedge_server_v4.py | head -1")
print(f"AUTO_TRADE: {out.strip()}")
out, _ = run("grep 'KILL_MAX_EXPOSURE' /root/polyclaw-bot/hedge_server_v4.py | head -1")
print(f"EXPOSURE: {out.strip()}")
out, _ = run("grep -A3 'def get_order_book' /root/polyclaw-bot/lib/clob_client.py")
print(f"OB fix: {out.strip()[:100]}")

# 2. Check .env
print("\n=== .ENV ===")
out, _ = run("cat /root/polyclaw-bot/.env")
print(out)

# 3. Check DB tables properly
print("=== DB TABLES ===")
test = textwrap.dedent("""
import sqlite3
conn = sqlite3.connect('/root/polyclaw-bot/data/hedge_bot.db')
cur = conn.cursor()
tables = cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print(f"Tables: {[t[0] for t in tables]}")
for t in tables:
    name = t[0]
    cnt = cur.execute(f"SELECT COUNT(*) FROM [{name}]").fetchone()[0]
    print(f"  {name}: {cnt} rows")
    if cnt > 0 and name in ('orders', 'incidents', 'depth_checks'):
        rows = cur.execute(f"SELECT * FROM [{name}] ORDER BY id DESC LIMIT 3").fetchall()
        cols = [d[0] for d in cur.description]
        print(f"    Cols: {cols}")
        for r in rows:
            print(f"    {r}")
""")
run(f"cat > /tmp/check_db.py << 'PYEOF'\n{test}\nPYEOF")
out, err = run("cd /root/polyclaw-bot && /root/.local/bin/uv run python /tmp/check_db.py 2>&1")
print(out)

# 4. Try manual CLOB order test from London
print("=== CLOB ORDER TEST FROM LONDON ===")
clob_test = textwrap.dedent("""
import os, json, asyncio
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
    
    # Get a market with liquidity
    events = await gamma.get_events(limit=10)
    for ev in events:
        for m in ev.markets[:2]:
            if m.yes_token_id and m.active and not m.closed and m.yes_price > 0.01 and m.yes_price < 0.99:
                print(f"Testing: {m.question[:50]}")
                print(f"Price: {m.yes_price}")
                tid = m.yes_token_id
                
                # Test order book
                ob = clob.get_order_book(tid)
                asks = ob.get('asks', [])
                print(f"Asks: {len(asks)}")
                
                if asks:
                    # Try placing a tiny $0.01 order (will be too small to fill, just test auth)
                    try:
                        from py_clob_client.clob_types import OrderArgs, OrderType
                        from py_clob_client.order_builder.constants import BUY
                        
                        order = clob.client.create_order(
                            OrderArgs(token_id=tid, price=0.01, size=1, side=BUY)
                        )
                        result = clob.client.post_order(order, OrderType.GTC)
                        print(f"ORDER PLACED! Result: {json.dumps(result)[:200]}")
                        
                        # Cancel it
                        oid = result.get('orderID', '')
                        if oid:
                            clob.client.cancel(oid)
                            print(f"Cancelled: {oid}")
                        return
                    except Exception as e:
                        print(f"ORDER ERROR: {e}")
                        return
    print("No suitable market found")

asyncio.run(main())
""")
run(f"cat > /tmp/test_order.py << 'PYEOF'\n{clob_test}\nPYEOF")
out, err = run("cd /root/polyclaw-bot && /root/.local/bin/uv run python /tmp/test_order.py 2>&1")
print(out)
if err:
    print("ERR:", err[-300:])

ssh.close()
