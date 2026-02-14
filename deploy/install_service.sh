#!/bin/bash
# ============================================
# Install systemd service for 24/7 operation
# Run as: sudo bash install_service.sh
# ============================================
set -e

BOT_DIR="$HOME/polyclaw-bot"
USER=$(whoami)
UV_PATH="$HOME/.local/bin/uv"

cat > /tmp/polyclaw-bot.service << EOF
[Unit]
Description=PolyClaw Hedge Server v4 — Full Execution Engine
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$BOT_DIR
ExecStart=$UV_PATH run python hedge_server_v4.py
Restart=always
RestartSec=30
Environment=PATH=$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin

# Logging
StandardOutput=journal
StandardError=journal

# Safety
Nice=10
MemoryMax=512M

[Install]
WantedBy=multi-user.target
EOF

sudo mv /tmp/polyclaw-bot.service /etc/systemd/system/polyclaw-bot.service
sudo systemctl daemon-reload
sudo systemctl enable polyclaw-bot.service
sudo systemctl start polyclaw-bot.service

echo "✅ Service installed and started!"
echo ""
echo "Commands:"
echo "  sudo systemctl status polyclaw-bot    # Check status"
echo "  sudo journalctl -u polyclaw-bot -f    # Live logs"
echo "  sudo systemctl restart polyclaw-bot   # Restart"
echo "  sudo systemctl stop polyclaw-bot      # Stop"
