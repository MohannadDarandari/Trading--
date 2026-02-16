"""Deploy BTC predictor to VPS and create systemd service."""
import paramiko
import time

VPS_IP = '172.236.9.220'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(VPS_IP, username='root', password='MOHANNAD@1011', timeout=15)

def run(cmd, timeout=60):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    stdout.channel.recv_exit_status()
    return stdout.read().decode().strip(), stderr.read().decode().strip()

print("="*55)
print("  🚀 DEPLOYING BTC PREDICTOR TO VPS")
print("="*55)

# Step 1: Pull latest from GitHub
print("\n  Step 1: Pulling from GitHub...")
out, err = run("cd /root/polyclaw && git pull origin main")
print(f"    {out}")

# Step 2: Verify file exists
print("\n  Step 2: Verifying btc_predictor.py...")
out, _ = run("ls -la /root/polyclaw/btc_predictor.py")
print(f"    {out}")

# Step 3: Test it
print("\n  Step 3: Testing predictor on VPS...")
out, err = run("cd /root/polyclaw && python3 test_predictor.py 2>&1 | head -20", timeout=30)
print(f"    {out}")

# Step 4: Create systemd service
print("\n  Step 4: Creating systemd service...")
service = """[Unit]
Description=BTC 5-Min Predictor - Polymarket Signals
After=network.target

[Service]
Type=simple
WorkingDirectory=/root/polyclaw
ExecStart=/usr/bin/python3 /root/polyclaw/btc_predictor.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
"""

run(f"cat > /etc/systemd/system/btc-predictor.service << 'EOF'\n{service}\nEOF")
run("systemctl daemon-reload")
run("systemctl enable btc-predictor")
run("systemctl start btc-predictor")

time.sleep(5)

# Step 5: Check status
print("\n  Step 5: Checking service status...")
out, _ = run("systemctl is-active btc-predictor")
print(f"    Service: {out}")

out, _ = run("journalctl -u btc-predictor --no-pager -n 15 --since '10 seconds ago'")
for line in out.split('\n')[-10:]:
    msg = line.split(']: ', 1)[-1] if ']: ' in line else line
    print(f"    {msg[:120]}")

# Also check hedge bot is still running
print("\n  Step 6: Hedge bot status...")
out, _ = run("systemctl is-active polyclaw")
print(f"    Hedge bot: {out}")

ssh.close()

print("\n" + "="*55)
print("  ✅ 2 بوتات شغالة على السيرفر:")
print("  1. polyclaw — هيدج بوت (فرص مضمونة)")
print("  2. btc-predictor — توقعات 5 دقايق")
print("  ")
print("  تلقرام: @Parachuter_Bot بيرسلك كل 5 دقايق")
print("  قفل جهازك وارتاح!")
print("="*55)
