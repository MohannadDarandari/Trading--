"""Check why bot alerts but doesn't execute trades."""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("172.233.220.24", username="root", password="MOHANNAD@1011")

def run(cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd)
    return stdout.read().decode(), stderr.read().decode()

# Check the execution logic in hedge_server_v4.py
print("=== CHECKING EXECUTION LOGIC ===")
out, _ = run("sed -n '1190,1250p' /root/polyclaw-bot/hedge_server_v4.py")
print(out)

print("\n=== CHECKING ALERT LOGIC ===")
out, _ = run("grep -n 'ALERTED\|EXECUTED\|SKIPPED\|execute\|alert' /root/polyclaw-bot/hedge_server_v4.py | head -20")
print(out)

print("\n=== CHECKING AUTO_TRADE LINE ===")
out, _ = run("sed -n '55,75p' /root/polyclaw-bot/hedge_server_v4.py")
print(out)

print("\n=== CHECKING WALLET BALANCE CHECK ===")
out, _ = run("grep -n 'balance\|USDC\|usdc_e\|wallet' /root/polyclaw-bot/hedge_server_v4.py | head -30")
print(out)

# Check the full execution flow
print("\n=== FULL TRADE EXECUTION SECTION ===")
out, _ = run("sed -n '1380,1500p' /root/polyclaw-bot/hedge_server_v4.py")
print(out)

ssh.close()
