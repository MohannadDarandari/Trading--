"""Check which USDC the bot uses and fix everything."""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("172.233.220.24", username="root", password="MOHANNAD@1011")

def run(cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd)
    return stdout.read().decode(), stderr.read().decode()

# 1. Check which USDC address the bot/py-clob-client uses
print("=" * 50)
print("CHECKING BOT's USDC ADDRESS")
print("=" * 50)

# Check in hedge_server_v4.py
out, _ = run("grep -n -i 'usdc\\|collateral\\|0x2791\\|0x3c499\\|token_address' /root/polyclaw-bot/hedge_server_v4.py | head -20")
print("hedge_server_v4.py:")
print(out)

# Check in lib/ files
out, _ = run("grep -rn -i 'usdc\\|collateral\\|0x2791\\|0x3c499' /root/polyclaw-bot/lib/ 2>/dev/null | head -20")
print("lib/ files:")
print(out)

# Check py-clob-client source for collateral address
out, _ = run("find /root/polyclaw-bot/.venv -name '*.py' -path '*/py_clob_client/*' | head -20")
print("\npy-clob-client files:")
print(out)

out, _ = run("grep -rn '0x2791\\|0x3c499\\|collateral\\|USDC' /root/polyclaw-bot/.venv/lib/python*/site-packages/py_clob_client/ 2>/dev/null | head -20")
print("\npy-clob-client USDC refs:")
print(out)

# Check the constants/config in py-clob-client
out, _ = run("cat /root/polyclaw-bot/.venv/lib/python*/site-packages/py_clob_client/constants.py 2>/dev/null | head -40")
print("\npy-clob-client constants.py:")
print(out)

ssh.close()
