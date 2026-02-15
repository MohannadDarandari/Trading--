"""Check London VPS: verify non-US region + check if trades execute."""
import paramiko, time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("172.236.9.220", username="root", password="MOHANNAD@1011")

def run(cmd, timeout=60):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode(), stderr.read().decode()

# 1. Confirm region
print("=== REGION CHECK ===")
out, _ = run("curl -s http://ip-api.com/json")
print(out)

# 2. Wait for next scan (3 min interval)
print("\n=== WAITING FOR NEXT SCAN (200 sec) ===")
time.sleep(200)

# 3. Check logs
print("=== LATEST LOGS ===")
out, _ = run("journalctl -u polyclaw-bot --no-pager -n 50 --output=cat")
print(out[-3000:])

# 4. Check DB for orders and errors
print("\n=== DB CHECK ===")
out, _ = run(
    "cd /root/polyclaw-bot && /root/.local/bin/uv run python -c \""
    "import sqlite3; conn = sqlite3.connect('data/hedge_bot.db'); "
    "cur = conn.cursor(); "
    "for t in ['orders','incidents','depth_checks','pnl']: "
    "  cur.execute(f'SELECT COUNT(*) FROM {t}'); "
    "  print(f'{t}: {cur.fetchone()[0]} rows'); "
    "cur.execute('SELECT status, error FROM orders ORDER BY id DESC LIMIT 5'); "
    "rows = cur.fetchall(); "
    "print(); "
    "[print(f'  {r}') for r in rows]; "
    "print() if rows else print('No orders yet'); "
    "cur.execute('SELECT incident_type, details, kill_reason FROM incidents ORDER BY id DESC LIMIT 3'); "
    "[print(f'  INC: {r}') for r in cur.fetchall()]"
    "\""
)
print(out)

ssh.close()
print("\nDONE!")
