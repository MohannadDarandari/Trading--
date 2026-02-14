#!/bin/bash
# ============================================================
#  FULL AUTO DEPLOY — Run this ONE command on VPS
#  Copies engine.py, installs service, starts bot
# ============================================================

set -e
cd /home/ubuntu

echo "🚀 DarkOps Trading Bot — Full Deploy"
echo "============================================"

# Setup
sudo apt update -qq && sudo apt install -y python3 python3-pip python3-venv -qq
mkdir -p ~/trading-bot
cd ~/trading-bot

# Virtual env
python3 -m venv venv 2>/dev/null || true
source venv/bin/activate
pip install -q --upgrade pip
pip install -q requests

# Check engine exists
if [ ! -f engine.py ]; then
    echo "❌ engine.py not found! Upload it first:"
    echo "   scp simulator/engine.py ubuntu@YOUR_VPS_IP:~/trading-bot/engine.py"
    exit 1
fi

# Install systemd service
sudo tee /etc/systemd/system/trading-bot.service > /dev/null << 'EOF'
[Unit]
Description=DarkOps Polymarket Trading Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/trading-bot
ExecStart=/home/ubuntu/trading-bot/venv/bin/python3 /home/ubuntu/trading-bot/engine.py
Restart=always
RestartSec=10
StandardOutput=append:/home/ubuntu/trading-bot/bot.log
StandardError=append:/home/ubuntu/trading-bot/bot.log
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable trading-bot
sudo systemctl restart trading-bot

echo ""
echo "============================================"
echo "  ✅ BOT DEPLOYED AND RUNNING 24/7!"
echo "============================================"
echo ""
echo "  Useful commands:"
echo "  📊 Check status:  sudo systemctl status trading-bot"
echo "  📝 View logs:     tail -f ~/trading-bot/bot.log"
echo "  🛑 Stop bot:      sudo systemctl stop trading-bot"
echo "  🔄 Restart bot:   sudo systemctl restart trading-bot"
echo ""
