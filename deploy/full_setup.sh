#!/bin/bash
# ============================================================
# PolyClaw Hedge Server v4 — ONE-CLICK VPS DEPLOYMENT
# Run this ONCE after uploading files to /root/polyclaw-bot/
# ============================================================
set -e

echo "🦞 PolyClaw VPS Full Setup Starting..."
echo "========================================"

# 1. Update system
echo "[1/7] Updating system..."
apt update && apt upgrade -y

# 2. Install essentials
echo "[2/7] Installing Python & essentials..."
apt install -y python3 python3-pip python3-venv curl unzip git

# 3. Install uv
echo "[3/7] Installing uv package manager..."
if ! command -v uv &>/dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc

# 4. Go to bot directory
echo "[4/7] Setting up bot directory..."
cd /root/polyclaw-bot

# 5. Install Python dependencies via uv
echo "[5/7] Installing Python dependencies..."
uv sync

# 6. Quick test (import check)
echo "[6/7] Testing imports..."
uv run python -c "
import httpx
from dotenv import load_dotenv
print('  ✅ httpx OK')
print('  ✅ dotenv OK')
try:
    from py_clob_client.client import ClobClient
    print('  ✅ py-clob-client OK')
except: print('  ⚠️ py-clob-client needs proxy')
try:
    from web3 import Web3
    print('  ✅ web3 OK')
except: print('  ⚠️ web3 issue')
print('All imports checked.')
"

# 7. Install systemd service
echo "[7/7] Installing systemd service..."
UV_PATH="$HOME/.local/bin/uv"

cat > /etc/systemd/system/polyclaw-bot.service << EOF
[Unit]
Description=PolyClaw Hedge Server v4 — Full Execution Engine
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/polyclaw-bot
ExecStart=$UV_PATH run python hedge_server_v4.py
Restart=always
RestartSec=30
Environment=PATH=/root/.local/bin:/usr/local/bin:/usr/bin:/bin

# Logging
StandardOutput=journal
StandardError=journal

# Safety limits
Nice=10
MemoryMax=512M

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable polyclaw-bot.service
systemctl start polyclaw-bot.service

echo ""
echo "========================================"
echo "🦞 PolyClaw Hedge Server v4 — DEPLOYED!"
echo "========================================"
echo ""
echo "✅ Bot is running 24/7 as a systemd service"
echo ""
echo "Commands:"
echo "  systemctl status polyclaw-bot      # Check status"
echo "  journalctl -u polyclaw-bot -f      # Live logs"
echo "  systemctl restart polyclaw-bot     # Restart"
echo "  systemctl stop polyclaw-bot        # Stop"
echo ""
echo "🔒 You can now close your PC. Bot runs on the server!"
echo "📱 Monitor via Telegram @Parachuter_Bot"
echo ""
