"""Activate live trading on VPS - check balances, update config, enable AUTO_TRADE."""
import paramiko
import time

VPS = "172.233.220.24"
USER = "root"
PASS = "MOHANNAD@1011"

def run(ssh, cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode()
    err = stderr.read().decode()
    return out, err

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(VPS, username=USER, password=PASS)
print("✅ Connected to VPS\n")

# 1. Check wallet balance
print("=" * 50)
print("📊 WALLET BALANCES")
print("=" * 50)
balance_script = r'''
cd /root/polyclaw-bot && /root/.local/bin/uv run python -c "
from web3 import Web3
w3 = Web3(Web3.HTTPProvider('https://polygon-mainnet.g.alchemy.com/v2/S9mnnjfuSy_gDGll0If76'))
wallet = '0xAdd5cf1e1d6992C0130C3a89094F300fA71d32E5'
pol = w3.eth.get_balance(wallet)
print(f'POL: {w3.from_wei(pol, chr(34)+\"ether\"+chr(34)):.4f} (gas)')
usdc_addr = '0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359'
usdc_abi = [{'inputs': [{'name': 'account', 'type': 'address'}], 'name': 'balanceOf', 'outputs': [{'name': '', 'type': 'uint256'}], 'stateMutability': 'view', 'type': 'function'}, {'inputs': [], 'name': 'decimals', 'outputs': [{'name': '', 'type': 'uint8'}], 'stateMutability': 'view', 'type': 'function'}]
usdc = w3.eth.contract(address=w3.to_checksum_address(usdc_addr), abi=usdc_abi)
bal = usdc.functions.balanceOf(w3.to_checksum_address(wallet)).call()
dec = usdc.functions.decimals().call()
print(f'USDC (native): {bal / 10**dec:.4f}')
usdce_addr = '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174'
usdce = w3.eth.contract(address=w3.to_checksum_address(usdce_addr), abi=usdc_abi)
bale = usdce.functions.balanceOf(w3.to_checksum_address(wallet)).call()
dece = usdce.functions.decimals().call()
print(f'USDC.e (bridged): {bale / 10**dece:.4f}')
"
'''
out, err = run(ssh, balance_script)
print(out)
if "Error" in err or "error" in err:
    print("⚠️", err[-300:])

# 2. Check current config
print("=" * 50)
print("⚙️ CURRENT CONFIG")
print("=" * 50)
out, err = run(ssh, "grep -n 'TRADE_BUDGET\|BANKROLL\|AUTO_TRADE\|MAX_SPREAD\|SCAN_INTERVAL' /root/polyclaw-bot/hedge_server_v4.py | head -20")
print(out)

# 3. Update config for $28 bankroll
print("=" * 50)
print("🔧 UPDATING CONFIG FOR $28 BANKROLL")
print("=" * 50)

# Update BANKROLL to 28
out, err = run(ssh, "sed -i 's/BANKROLL = .*/BANKROLL = 28/' /root/polyclaw-bot/hedge_server_v4.py")
print("✅ BANKROLL = 28")

# Update TRADE_BUDGET to 3 (conservative)
out, err = run(ssh, "sed -i 's/TRADE_BUDGET = .*/TRADE_BUDGET = 3/' /root/polyclaw-bot/hedge_server_v4.py")
print("✅ TRADE_BUDGET = 3")

# Enable AUTO_TRADE
out, err = run(ssh, "sed -i 's/AUTO_TRADE = .*/AUTO_TRADE = True/' /root/polyclaw-bot/hedge_server_v4.py")
print("✅ AUTO_TRADE = True")

# Also set in .env
out, err = run(ssh, "grep -q 'AUTO_TRADE' /root/polyclaw-bot/.env && sed -i 's/AUTO_TRADE=.*/AUTO_TRADE=true/' /root/polyclaw-bot/.env || echo 'AUTO_TRADE=true' >> /root/polyclaw-bot/.env")
print("✅ .env AUTO_TRADE=true")

out, err = run(ssh, "grep -q 'BANKROLL' /root/polyclaw-bot/.env && sed -i 's/BANKROLL=.*/BANKROLL=28/' /root/polyclaw-bot/.env || echo 'BANKROLL=28' >> /root/polyclaw-bot/.env")
print("✅ .env BANKROLL=28")

out, err = run(ssh, "grep -q 'TRADE_BUDGET' /root/polyclaw-bot/.env && sed -i 's/TRADE_BUDGET=.*/TRADE_BUDGET=3/' /root/polyclaw-bot/.env || echo 'TRADE_BUDGET=3' >> /root/polyclaw-bot/.env")
print("✅ .env TRADE_BUDGET=3")

# 4. Verify updated config
print("\n" + "=" * 50)
print("✅ VERIFY UPDATED CONFIG")
print("=" * 50)
out, err = run(ssh, "grep -n 'TRADE_BUDGET\|BANKROLL\|AUTO_TRADE' /root/polyclaw-bot/hedge_server_v4.py | head -10")
print(out)
out, err = run(ssh, "cat /root/polyclaw-bot/.env")
print(out)

# 5. Restart bot
print("=" * 50)
print("🔄 RESTARTING BOT...")
print("=" * 50)
out, err = run(ssh, "systemctl restart polyclaw-bot")
time.sleep(3)
out, err = run(ssh, "systemctl status polyclaw-bot --no-pager -l")
print(out)

# 6. Wait and check first scan
print("=" * 50)
print("⏳ WAITING FOR FIRST SCAN (15 sec)...")
print("=" * 50)
time.sleep(15)
out, err = run(ssh, "journalctl -u polyclaw-bot --no-pager -n 30")
print(out)

ssh.close()
print("\n🎉 DONE! Bot is now LIVE TRADING with $28 USDC!")
