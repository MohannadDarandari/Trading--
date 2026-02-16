"""Check if the predictor is sending signals."""
import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('172.236.9.220', username='root', password='MOHANNAD@1011', timeout=15)

print("  Waiting 2 minutes for next signal cycle...")
time.sleep(120)

print("\n  📜 Predictor logs (last 2 minutes):")
stdin, stdout, stderr = ssh.exec_command(
    "journalctl -u btc-predictor --no-pager -n 30 --since '3 minutes ago'",
    timeout=10
)
stdout.channel.recv_exit_status()
logs = stdout.read().decode().strip()
for line in logs.split('\n'):
    msg = line.split(']: ', 1)[-1] if ']: ' in line else line
    print(f"    {msg[:130]}")

# Check both services
print("\n  📊 Service Status:")
for svc in ['polyclaw', 'btc-predictor']:
    stdin, stdout, _ = ssh.exec_command(f"systemctl is-active {svc}", timeout=5)
    status = stdout.read().decode().strip()
    print(f"    {svc}: {status}")

ssh.close()
