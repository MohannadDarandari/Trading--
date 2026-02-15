"""
Deploy PolyClaw bot to London VPS.
Usage: py deploy_london.py <NEW_IP> <ROOT_PASSWORD>
"""
import paramiko
import sys
import time

if len(sys.argv) < 3:
    print("Usage: py deploy_london.py <NEW_IP> <ROOT_PASSWORD>")
    sys.exit(1)

NEW_IP = sys.argv[1]
ROOT_PASS = sys.argv[2]

print(f"=== Deploying to London VPS: {NEW_IP} ===\n")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(NEW_IP, username="root", password=ROOT_PASS, timeout=30)

def run(cmd, timeout=300):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    return out, err

# 1. Verify region
print("[1/8] Checking region...")
out, _ = run("curl -s http://ip-api.com/json | python3 -c \"import sys,json; d=json.load(sys.stdin); print(f'{d[\"country\"]} - {d[\"city\"]}')\"")
print(f"  Region: {out.strip()}")
if "United States" in out:
    print("  ❌ STILL IN US! Aborting.")
    ssh.close()
    sys.exit(1)
print("  ✅ Non-US region confirmed!")

# 2. Install dependencies
print("\n[2/8] Installing system dependencies...")
run("apt update -qq && apt install -y -qq git python3-pip curl > /dev/null 2>&1", timeout=120)
print("  ✅ System packages ready")

# 3. Install uv
print("\n[3/8] Installing uv...")
out, _ = run("which uv 2>/dev/null || (curl -LsSf https://astral.sh/uv/install.sh | sh && echo 'INSTALLED')")
if "INSTALLED" in out:
    print("  ✅ uv installed fresh")
else:
    print("  ✅ uv already installed")

# 4. Clone repo
print("\n[4/8] Cloning bot repo...")
run("rm -rf /root/polyclaw-bot")
out, err = run("git clone https://github.com/MohannadDarandari/Trading--.git /root/polyclaw-bot 2>&1")
print(f"  {out.strip()}")
print("  ✅ Repo cloned")

# 5. Setup Python environment
print("\n[5/8] Setting up Python environment...")
out, err = run("cd /root/polyclaw-bot && /root/.local/bin/uv venv && /root/.local/bin/uv pip install -r requirements.txt 2>&1", timeout=180)
# Check if requirements.txt exists, otherwise install manually
if "No such file" in err or "error" in err.lower():
    print("  Installing packages manually...")
    out, err = run(
        "cd /root/polyclaw-bot && /root/.local/bin/uv pip install "
        "py-clob-client==0.34.5 httpx python-dotenv aiohttp web3 2>&1",
        timeout=180
    )
print("  ✅ Python environment ready")

# 6. Create .env
print("\n[6/8] Creating .env...")
env_content = """# PolyClaw Configuration
CHAINSTACK_NODE=https://polygon-mainnet.g.alchemy.com/v2/S9mnnjfuSy_gDGll0If76
OPENROUTER_API_KEY=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
POLYCLAW_PRIVATE_KEY=33b0c6d92c974489686742b4af56e168530a3f1d794a3c2c23831c59d8a369e9
AUTO_TRADE=true
BANKROLL=28
TRADE_BUDGET=2
"""
run(f"cat > /root/polyclaw-bot/.env << 'EOF'\n{env_content}\nEOF")
print("  ✅ .env configured")

# 7. Create systemd service
print("\n[7/8] Creating systemd service...")
service = """[Unit]
Description=PolyClaw Hedge Server v4
After=network.target

[Service]
Type=simple
WorkingDirectory=/root/polyclaw-bot
ExecStart=/root/.local/bin/uv run python hedge_server_v4.py
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
"""
run(f"cat > /etc/systemd/system/polyclaw-bot.service << 'EOF'\n{service}\nEOF")
run("systemctl daemon-reload && systemctl enable polyclaw-bot")
print("  ✅ Systemd service created")

# 8. Setup auto-deploy cron
print("\n[8/8] Setting up auto-deploy...")
cron_script = """#!/bin/bash
cd /root/polyclaw-bot
git fetch origin main --quiet
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)
if [ "$LOCAL" != "$REMOTE" ]; then
    git pull origin main --quiet
    systemctl restart polyclaw-bot
    echo "$(date): Updated and restarted" >> /var/log/polyclaw-deploy.log
fi
"""
run(f"cat > /root/auto-deploy.sh << 'EOF'\n{cron_script}\nEOF")
run("chmod +x /root/auto-deploy.sh")
run("(crontab -l 2>/dev/null | grep -v auto-deploy; echo '*/2 * * * * /root/auto-deploy.sh') | crontab -")
print("  ✅ Auto-deploy cron ready (every 2 min)")

# 9. Create data dir and start
print("\n=== STARTING BOT ===")
run("mkdir -p /root/polyclaw-bot/data")
run("systemctl start polyclaw-bot")
time.sleep(20)

out, _ = run("journalctl -u polyclaw-bot --no-pager -n 30 --output=cat")
print(out)

# 10. Final verification
print("\n=== VERIFICATION ===")
out, _ = run("systemctl is-active polyclaw-bot")
print(f"Service: {out.strip()}")
out, _ = run("curl -s http://ip-api.com/json | python3 -c \"import sys,json; d=json.load(sys.stdin); print(f'{d[\"country\"]} ({d[\"city\"]})')\"")
print(f"Location: {out.strip()}")

ssh.close()
print("\n🎉 DEPLOYMENT COMPLETE! Bot running from London!")
print(f"Monitor: ssh root@{NEW_IP}")
print(f"Logs: journalctl -u polyclaw-bot -f")
