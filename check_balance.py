"""Check wallet balance and bot execution status."""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("172.233.220.24", username="root", password="MOHANNAD@1011")

def run(cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd)
    return stdout.read().decode(), stderr.read().decode()

# 1. Wallet balance check
print("=" * 50)
print("WALLET BALANCES")
print("=" * 50)

script = (
    'cd /root/polyclaw-bot && /root/.local/bin/uv run python -c "'
    "from web3 import Web3;"
    "w3 = Web3(Web3.HTTPProvider('https://polygon-mainnet.g.alchemy.com/v2/S9mnnjfuSy_gDGll0If76'));"
    "wallet = '0xAdd5cf1e1d6992C0130C3a89094F300fA71d32E5';"
    "pol = w3.eth.get_balance(wallet);"
    "pol_val = float(w3.from_wei(pol, 'ether'));"
    "print(f'POL: {pol_val:.4f}');"
    "usdc_abi = [{'inputs': [{'name': 'account', 'type': 'address'}], 'name': 'balanceOf', 'outputs': [{'name': '', 'type': 'uint256'}], 'stateMutability': 'view', 'type': 'function'}];"
    "usdc = w3.eth.contract(address=w3.to_checksum_address('0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359'), abi=usdc_abi);"
    "usdc_bal = usdc.functions.balanceOf(w3.to_checksum_address(wallet)).call();"
    "print(f'USDC native: {usdc_bal / 1e6:.4f}');"
    "usdce = w3.eth.contract(address=w3.to_checksum_address('0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174'), abi=usdc_abi);"
    "usdce_bal = usdce.functions.balanceOf(w3.to_checksum_address(wallet)).call();"
    "print(f'USDC.e bridged: {usdce_bal / 1e6:.4f}');"
    '"'
)
out, err = run(script)
print(out)
if err and ("Error" in err or "Traceback" in err):
    print("ERR:", err[-500:])

# 2. Check bot USDC address
print("=" * 50)
print("BOT USDC CONFIG")
print("=" * 50)
out, _ = run("grep -i 'usdc\\|0x2791\\|0x3c499\\|COLLATERAL' /root/polyclaw-bot/hedge_server_v4.py | head -15")
print(out)

# 3. Check if bot tried to execute trades
print("=" * 50)
print("RECENT LOGS (last 20 lines)")
print("=" * 50)
out, _ = run("journalctl -u polyclaw-bot --no-pager -n 20 --output=cat")
print(out)

# 4. Check if approvals set
print("=" * 50)
print("CHECKING APPROVALS")
print("=" * 50)
approval_script = (
    'cd /root/polyclaw-bot && /root/.local/bin/uv run python -c "'
    "from web3 import Web3;"
    "w3 = Web3(Web3.HTTPProvider('https://polygon-mainnet.g.alchemy.com/v2/S9mnnjfuSy_gDGll0If76'));"
    "wallet = '0xAdd5cf1e1d6992C0130C3a89094F300fA71d32E5';"
    "approve_abi = [{'inputs': [{'name': 'owner', 'type': 'address'}, {'name': 'spender', 'type': 'address'}], 'name': 'allowance', 'outputs': [{'name': '', 'type': 'uint256'}], 'stateMutability': 'view', 'type': 'function'}];"
    "usdce = w3.eth.contract(address=w3.to_checksum_address('0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174'), abi=approve_abi);"
    "ctf = '0x4D97DCd97eC945f40cF65F87097ACe5EA0476045';"
    "neg_risk = '0xC5d563A36AE78145C45a50134d48A1215220f80a';"
    "allowance_ctf = usdce.functions.allowance(w3.to_checksum_address(wallet), w3.to_checksum_address(ctf)).call();"
    "allowance_neg = usdce.functions.allowance(w3.to_checksum_address(wallet), w3.to_checksum_address(neg_risk)).call();"
    "print(f'USDC.e -> CTF Exchange: {allowance_ctf}');"
    "print(f'USDC.e -> NegRisk: {allowance_neg}');"
    "print(f'Approved: {allowance_ctf > 0 and allowance_neg > 0}');"
    '"'
)
out, err = run(approval_script)
print(out)
if err and ("Error" in err or "Traceback" in err):
    print("ERR:", err[-500:])

ssh.close()
