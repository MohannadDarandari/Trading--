"""Read CLOB wrapper, depth check, and lines around api_error recording."""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("172.233.220.24", username="root", password="MOHANNAD@1011")

def run(cmd, timeout=60):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode(), stderr.read().decode()

# 1. Lines around 1170-1190 (api_error at line 1179)
print("=== CONTEXT AROUND LINE 1179 ===")
out, _ = run("sed -n '1150,1195p' /root/polyclaw-bot/hedge_server_v4.py")
print(out)

# 2. Lines around 1580-1600 (api_error at line 1585)
print("=== CONTEXT AROUND LINE 1585 ===")
out, _ = run("sed -n '1570,1600p' /root/polyclaw-bot/hedge_server_v4.py")
print(out)

# 3. Check the CLOB class/wrapper (buy_gtc method)
print("=== CLOB CLIENT CLASS ===")
out, _ = run("grep -n 'class.*Clob\\|def buy_gtc\\|def.*clob\\|ClobClient' /root/polyclaw-bot/hedge_server_v4.py")
print(out)

# 4. Read the CLOB wrapper
print("=== CLOB WRAPPER CODE ===")
out, _ = run("grep -n 'class ClobWrapper\\|class SafeClob\\|class CLOB' /root/polyclaw-bot/hedge_server_v4.py")
print(out)

# 5. Find the buy_gtc implementation
print("=== buy_gtc IMPLEMENTATION ===")
out, _ = run("grep -n 'def buy_gtc' /root/polyclaw-bot/hedge_server_v4.py")
print(out)

# 6. Read around that function
out_line, _ = run("grep -n 'def buy_gtc' /root/polyclaw-bot/hedge_server_v4.py | head -1 | cut -d: -f1")
line_num = int(out_line.strip()) if out_line.strip().isdigit() else 0
if line_num > 0:
    print(f"\n=== buy_gtc at line {line_num} ===")
    out, _ = run(f"sed -n '{line_num},{line_num+50}p' /root/polyclaw-bot/hedge_server_v4.py")
    print(out)

# 7. _check_depth function
print("=== _check_depth FUNCTION ===")
out, _ = run("grep -n 'def _check_depth' /root/polyclaw-bot/hedge_server_v4.py")
print(out)
out_line, _ = run("grep -n 'def _check_depth' /root/polyclaw-bot/hedge_server_v4.py | head -1 | cut -d: -f1")
line_num = int(out_line.strip()) if out_line.strip().isdigit() else 0
if line_num > 0:
    out, _ = run(f"sed -n '{line_num},{line_num+35}p' /root/polyclaw-bot/hedge_server_v4.py")
    print(out)

# 8. Check DB orders table for actual errors
print("=== DB ORDERS WITH ERRORS ===")
out, _ = run(
    "cd /root/polyclaw-bot && /root/.local/bin/uv run python -c \""
    "import sqlite3; conn = sqlite3.connect('data/hedge_bot.db'); "
    "cur = conn.cursor(); "
    "cur.execute('SELECT opp_name, status, error, latency_ms FROM orders ORDER BY id DESC LIMIT 10'); "
    "rows = cur.fetchall(); "
    "[print(r) for r in rows]; "
    "print(f'Total: {len(rows)} orders') if rows else print('No orders yet')"
    "\""
)
print(out)

# 9. Check incidents table
print("=== DB INCIDENTS ===")
out, _ = run(
    "cd /root/polyclaw-bot && /root/.local/bin/uv run python -c \""
    "import sqlite3; conn = sqlite3.connect('data/hedge_bot.db'); "
    "cur = conn.cursor(); "
    "cur.execute('SELECT ts, incident_type, details, extra FROM incidents ORDER BY id DESC LIMIT 10'); "
    "rows = cur.fetchall(); "
    "[print(r) for r in rows]; "
    "print(f'Total: {len(rows)}') if rows else print('No incidents')"
    "\""
)
print(out)

ssh.close()
