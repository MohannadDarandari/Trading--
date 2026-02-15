"""Debug why bot shows ALERTED not EXECUTED despite TRADE_BUDGET fix."""
import paramiko, time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("172.233.220.24", username="root", password="MOHANNAD@1011")

def run(cmd, timeout=60):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode(), stderr.read().decode()

# 1. Find the execute_hedge method and what decides ALERTED vs EXECUTED
print("=== SEARCHING EXECUTE LOGIC ===")
out, _ = run("grep -n 'ALERTED\\|EXECUTED\\|execute_hedge\\|can_take_trade\\|exposure\\|depth\\|kill' /root/polyclaw-bot/hedge_server_v4.py | head -50")
print(out)

# 2. Check the exact execution decision block
print("=== EXECUTION DECISION CODE ===")
out, _ = run("sed -n '1370,1430p' /root/polyclaw-bot/hedge_server_v4.py")
print(out)

# 3. Also check the scan result handler (where ALERTED is printed)
print("=== ALERT OUTPUT CODE ===")
out, _ = run("grep -n 'ALERTED' /root/polyclaw-bot/hedge_server_v4.py")
print(out)

# 4. Check what calls execute_hedge
print("=== CALLS TO execute_hedge ===")
out, _ = run("grep -n 'execute_hedge\\|exec_report' /root/polyclaw-bot/hedge_server_v4.py | head -20")
print(out)

# 5. Check if there is some scan_and_execute vs scan_only logic
print("=== AUTO_TRADE CONDITIONAL ===")
out, _ = run("grep -n -A5 'AUTO_TRADE' /root/polyclaw-bot/hedge_server_v4.py | head -40")
print(out)

# 6. Check recent logs more carefully  
print("=== FULL RECENT LOGS ===")
out, _ = run("journalctl -u polyclaw-bot --no-pager -n 60 --output=cat")
print(out)

ssh.close()
