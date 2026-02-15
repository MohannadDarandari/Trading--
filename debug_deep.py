"""Deep debug: read execute_hedge function + check API error details."""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("172.233.220.24", username="root", password="MOHANNAD@1011")

def run(cmd, timeout=60):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode(), stderr.read().decode()

# 1. Read the execute_hedge function (lines 1182-1320)
print("=== EXECUTE_HEDGE FUNCTION ===")
out, _ = run("sed -n '1182,1320p' /root/polyclaw-bot/hedge_server_v4.py")
print(out)

# 2. Check what triggers api_error counting
print("=== API ERROR TRACKING ===")
out, _ = run("grep -n 'api_error\\|add_api_error\\|record_api_error' /root/polyclaw-bot/hedge_server_v4.py")
print(out)

# 3. Check DB for logged errors
print("=== DB ERROR LOGS ===")
out, _ = run(
    'cd /root/polyclaw-bot && /root/.local/bin/uv run python -c "'
    "import sqlite3; "
    "conn = sqlite3.connect('data/hedge_bot.db'); "
    "cur = conn.cursor(); "
    "tables = [r[0] for r in cur.execute('SELECT name FROM sqlite_master WHERE type=chr(39)+chr(116)+chr(97)+chr(98)+chr(108)+chr(101)+chr(39)').fetchall()]; "
    "print('Tables:', tables); "
    "[print(f'{t}: {cur.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]} rows') for t in tables]; "
    '"'
)
print(out)

# 4. Try simpler DB check
print("=== DB TABLES ===")
out, _ = run(
    "cd /root/polyclaw-bot && /root/.local/bin/uv run python -c \""
    "import sqlite3;"
    "conn = sqlite3.connect('data/hedge_bot.db');"
    "cur = conn.cursor();"
    "tables = cur.execute(\\\"SELECT name FROM sqlite_master WHERE type='table'\\\").fetchall();"
    "print(tables);"
    "\""
)
print(out)

# 5. Check KILL_API_ERRORS_10M threshold
print("=== KILL THRESHOLDS ===")
out, _ = run("grep -n 'KILL_\\|api_error' /root/polyclaw-bot/hedge_server_v4.py | head -25")
print(out)

# 6. Full journal since restart
print("=== FULL JOURNAL ===")
out, _ = run("journalctl -u polyclaw-bot --since '2 hours ago' --no-pager --output=cat | grep -i 'error\\|kill\\|fail\\|exception\\|traceback\\|EXECUTED\\|api' | head -30")
print(out)

ssh.close()
