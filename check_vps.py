"""Check VPS bot logs and status."""
import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('172.236.9.220', username='root', password='MOHANNAD@1011', timeout=15)

print("="*60)
print("  📊 VPS BOT STATUS")
print("="*60)

# Service status
stdin, stdout, stderr = ssh.exec_command("systemctl is-active polyclaw", timeout=5)
status = stdout.read().decode().strip()
print(f"\n  Service: {status}")

# Uptime
stdin, stdout, stderr = ssh.exec_command("systemctl show polyclaw --property=ActiveEnterTimestamp", timeout=5)
uptime = stdout.read().decode().strip()
print(f"  {uptime}")

# Memory usage
stdin, stdout, stderr = ssh.exec_command("ps aux | grep hedge_server | grep -v grep | awk '{print $4\"%\"}'", timeout=5)
mem = stdout.read().decode().strip()
print(f"  Memory: {mem}")

# Recent scan results
print("\n  📜 Recent Logs (last scan):")
stdin, stdout, stderr = ssh.exec_command(
    "journalctl -u polyclaw --no-pager -n 50 --since '5 minutes ago'",
    timeout=10
)
logs = stdout.read().decode().strip()
for line in logs.split('\n'):
    # Clean up timestamp
    if 'python3' in line:
        msg = line.split('python3[')[1].split(']: ', 1)[-1] if 'python3[' in line else line
        print(f"    {msg[:120]}")

ssh.close()
print("\n  ✅ VPS check complete!")
