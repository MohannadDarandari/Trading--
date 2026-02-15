"""Read lib/clob_client.py and check token_id population in opportunities."""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("172.233.220.24", username="root", password="MOHANNAD@1011")

def run(cmd, timeout=60):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode(), stderr.read().decode()

# 1. Full CLOB client wrapper
print("=== lib/clob_client.py ===")
out, _ = run("cat /root/polyclaw-bot/lib/clob_client.py")
print(out)

# 2. Check how markets populate token_id
print("=== TOKEN_ID POPULATION ===")
out, _ = run("grep -n 'token_id' /root/polyclaw-bot/hedge_server_v4.py | head -30")
print(out)

# 3. Check HedgeOpportunity dataclass
print("=== HedgeOpportunity CLASS ===")
out, _ = run("grep -n 'class HedgeOpportunity\\|token_id\\|markets' /root/polyclaw-bot/hedge_server_v4.py | head -20")
print(out)

# 4. Find HedgeOpportunity definition
out_line, _ = run("grep -n 'class HedgeOpportunity' /root/polyclaw-bot/hedge_server_v4.py | head -1 | cut -d: -f1")
line_num = int(out_line.strip()) if out_line.strip().isdigit() else 0
if line_num > 0:
    print(f"\n=== HedgeOpportunity at line {line_num} ===")
    out, _ = run(f"sed -n '{line_num},{line_num+30}p' /root/polyclaw-bot/hedge_server_v4.py")
    print(out)

# 5. Where "KILLED" message is printed
print("=== WHERE KILLED IS PRINTED ===")
out, _ = run("grep -n 'KILLED' /root/polyclaw-bot/hedge_server_v4.py")
print(out)

# 6. Check recent full log output more carefully - get ALL from last restart
print("=== ALL LOGS FROM LATEST RESTART ===")
out, _ = run("journalctl -u polyclaw-bot --no-pager -n 80 --output=cat")
print(out[-3000:])

ssh.close()
