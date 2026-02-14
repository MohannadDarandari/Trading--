#!/bin/bash
# ============================================================
#  DarkOps Trading Bot — One-Click VPS Deploy
#  Run this on your Oracle Free VPS (Ubuntu)
# ============================================================

set -e

echo "============================================================"
echo "  DARKOPS TRADING BOT — VPS SETUP"
echo "============================================================"

# 1. Update system
echo "[1/5] Updating system..."
sudo apt update && sudo apt upgrade -y

# 2. Install Python 3.10+
echo "[2/5] Installing Python..."
sudo apt install -y python3 python3-pip python3-venv git

# 3. Create project directory
echo "[3/5] Setting up project..."
mkdir -p ~/trading-bot
cd ~/trading-bot

# 4. Create virtual environment
echo "[4/5] Creating Python environment..."
python3 -m venv venv
source venv/bin/activate

# 5. Install dependencies
echo "[5/5] Installing packages..."
pip install --upgrade pip
pip install requests

echo ""
echo "============================================================"
echo "  ✅ SETUP COMPLETE!"
echo "  Now copy your engine.py file and run:"
echo "  sudo systemctl start trading-bot"
echo "============================================================"
