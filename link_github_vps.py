"""Clone GitHub repo on London VPS and link the bot service to it."""
import paramiko
import time

VPS_IP = '172.236.9.220'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(VPS_IP, username='root', password='MOHANNAD@1011', timeout=15)

def run(cmd, timeout=60):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    stdout.channel.recv_exit_status()
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    return out, err

print("="*55)
print("  📦 LINKING GITHUB TO LONDON VPS")
print("="*55)

# Step 1: Install git
print("\n  Step 1: Installing git...")
out, err = run("which git || apt-get install -y -qq git 2>/dev/null && git --version")
print(f"    {out}")

# Step 2: Stop bot service
print("\n  Step 2: Stopping bot...")
run("systemctl stop polyclaw")

# Step 3: Backup current .env
print("\n  Step 3: Backing up .env...")
run("cp /root/polyclaw/.env /root/polyclaw_env_backup 2>/dev/null")

# Step 4: Remove old manual deploy
print("\n  Step 4: Removing old manual files...")
run("rm -rf /root/polyclaw")

# Step 5: Clone repo
print("\n  Step 5: Cloning repo...")
out, err = run("git clone https://github.com/MohannadDarandari/Trading--.git /root/polyclaw", timeout=120)
print(f"    {out}")
if err:
    print(f"    {err[:200]}")

# Step 6: Restore .env
print("\n  Step 6: Restoring .env...")
run("cp /root/polyclaw_env_backup /root/polyclaw/.env 2>/dev/null")
# Also make sure data dir exists
run("mkdir -p /root/polyclaw/data")

# Step 7: Verify files
print("\n  Step 7: Verifying files...")
out, _ = run("ls -la /root/polyclaw/hedge_server_v4.py /root/polyclaw/lib/clob_client.py /root/polyclaw/.env 2>&1")
for line in out.split('\n'):
    print(f"    {line}")

# Step 8: Test imports
print("\n  Step 8: Testing imports...")
out, err = run("cd /root/polyclaw && python3 -c 'from lib.gamma_client import GammaClient; from lib.clob_client import ClobClientWrapper; print(\"ALL OK\")'")
print(f"    {out}")
if err and 'Warning' not in err:
    print(f"    ERR: {err[:200]}")

# Step 9: Update systemd service to point to new path
print("\n  Step 9: Updating systemd service...")
service = """[Unit]
Description=PolyClaw Hedge Bot v4
After=network.target

[Service]
Type=simple
WorkingDirectory=/root/polyclaw
ExecStart=/usr/bin/python3 /root/polyclaw/hedge_server_v4.py
Restart=always
RestartSec=30
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
"""
run(f"cat > /etc/systemd/system/polyclaw.service << 'EOF'\n{service}\nEOF")
run("systemctl daemon-reload")

# Step 10: Create auto-update script
print("\n  Step 10: Creating auto-update script...")
update_script = """#!/bin/bash
# Pull latest from GitHub and restart bot
cd /root/polyclaw
git pull origin main
systemctl restart polyclaw
echo "Updated and restarted!"
journalctl -u polyclaw --no-pager -n 5
"""
run(f"cat > /root/update_bot.sh << 'EOF'\n{update_script}\nEOF")
run("chmod +x /root/update_bot.sh")

# Step 11: Start bot
print("\n  Step 11: Starting bot...")
run("systemctl start polyclaw")
time.sleep(8)

# Step 12: Verify
print("\n  Step 12: Verifying...")
out, _ = run("systemctl is-active polyclaw")
print(f"    Service: {out}")

out, _ = run("journalctl -u polyclaw --no-pager -n 15 --since '15 seconds ago' | grep -E 'Wallet|CLOB|Scan|Found|ALERTED|error'")
for line in out.split('\n')[-10:]:
    msg = line.split(']: ', 1)[-1] if ']: ' in line else line
    print(f"    {msg[:120]}")

# Show git info
out, _ = run("cd /root/polyclaw && git log --oneline -3")
print(f"\n  📌 Git commits on VPS:")
for line in out.split('\n'):
    print(f"    {line}")

ssh.close()

print("\n" + "="*55)
print("  ✅ GitHub مرتبط بالسيرفر!")
print("  ")
print("  للتحديث لاحقاً:")
print("  1. سوي push من جهازك: git push")
print("  2. شغّل على السيرفر: ssh root@172.236.9.220 bash /root/update_bot.sh")
print("="*55)
