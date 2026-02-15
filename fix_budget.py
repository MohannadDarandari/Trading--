"""Fix TRADE_BUDGET exposure limit issue and restart bot."""
import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("172.233.220.24", username="root", password="MOHANNAD@1011")

def run(cmd, timeout=60):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode(), stderr.read().decode()

# Fix TRADE_BUDGET from 3 to 2 (must be < BANKROLL * max_open_exposure_pct = 28 * 0.10 = 2.80)
print("=== FIXING TRADE_BUDGET ===")
run("sed -i 's/TRADE_BUDGET = 3/TRADE_BUDGET = 2/' /root/polyclaw-bot/hedge_server_v4.py")
run("sed -i 's/TRADE_BUDGET=3/TRADE_BUDGET=2/' /root/polyclaw-bot/.env")

# Verify
out, _ = run("grep 'TRADE_BUDGET' /root/polyclaw-bot/hedge_server_v4.py | head -3")
print(f"Code: {out.strip()}")
out, _ = run("grep 'TRADE_BUDGET' /root/polyclaw-bot/.env")
print(f".env: {out.strip()}")

# Check for recent execution errors in DB
print("\n=== RECENT DB INCIDENTS ===")
db_check = (
    'cd /root/polyclaw-bot && /root/.local/bin/uv run python -c "'
    "import sqlite3;"
    "conn = sqlite3.connect('data/hedge_bot.db');"
    "cur = conn.cursor();"
    "cur.execute('SELECT ts, incident_type, details FROM incidents ORDER BY id DESC LIMIT 5');"
    "rows = cur.fetchall();"
    "for r in rows: print(f'{r[0]} | {r[1]} | {r[2]}');"
    "if not rows: print('No incidents yet');"
    "print();"
    "cur.execute('SELECT COUNT(*) FROM orders');"
    "print(f'Total orders: {cur.fetchone()[0]}');"
    "cur.execute('SELECT COUNT(*) FROM orders WHERE status=chr(39)+chr(102)+chr(105)+chr(108)+chr(108)+chr(101)+chr(100)+chr(39)');"
    "print(f'Filled orders: {cur.fetchone()[0]}');"
    "cur.execute('SELECT COUNT(*) FROM orders WHERE error IS NOT NULL AND error != chr(39)+chr(39)');"
    "print(f'Error orders: {cur.fetchone()[0]}');"
    '"'
)
out, err = run(db_check)
print(out)
if "Error" in str(err): print("ERR:", err[-200:])

# Restart bot
print("=== RESTARTING BOT ===")
run("systemctl restart polyclaw-bot")
time.sleep(5)

out, _ = run("systemctl status polyclaw-bot --no-pager")
for line in out.split("\n"):
    if "Active:" in line or "Budget:" in line or "Auto-trade:" in line:
        print(f"  {line.strip()}")

# Wait for first scan + execution attempt
print("\n=== WAITING FOR EXECUTION (25 sec) ===")
time.sleep(25)

out, _ = run("journalctl -u polyclaw-bot --no-pager -n 35 --output=cat")
print(out)

ssh.close()
print("\nDONE!")
