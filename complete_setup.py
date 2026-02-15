"""
COMPLETE SETUP: Swap USDC native -> USDC.e + Set Polymarket approvals.
All done programmatically from VPS using the private key.
"""
import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("172.233.220.24", username="root", password="MOHANNAD@1011")

def run(cmd, timeout=60):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode(), stderr.read().decode()

# Upload and run comprehensive setup script on VPS
setup_script = r'''
import json, time, os, sys
from web3 import Web3
from eth_account import Account

RPC = "https://polygon-mainnet.g.alchemy.com/v2/S9mnnjfuSy_gDGll0If76"
PK = "33b0c6d92c974489686742b4af56e168530a3f1d794a3c2c23831c59d8a369e9"

USDC_NATIVE = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"
USDC_E = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"

# Polymarket contracts
CTF = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
CTF_EXCHANGE = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
NEG_RISK_CTF_EXCHANGE = "0xC5d563A36AE78145C45a50134d48A1215220f80a"
NEG_RISK_ADAPTER = "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296"

# Uniswap V3 SwapRouter on Polygon
SWAP_ROUTER = "0xE592427A0AEce92De3Edee1F18E0157C05861564"

MAX_UINT256 = 2**256 - 1

ERC20_ABI = json.loads('[{"inputs":[{"name":"spender","type":"address"},{"name":"amount","type":"uint256"}],"name":"approve","outputs":[{"name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"name":"owner","type":"address"},{"name":"spender","type":"address"}],"name":"allowance","outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"name":"account","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"stateMutability":"view","type":"function"}]')

# Uniswap V3 exactInputSingle ABI
SWAP_ABI = json.loads('[{"inputs":[{"components":[{"name":"tokenIn","type":"address"},{"name":"tokenOut","type":"address"},{"name":"fee","type":"uint24"},{"name":"recipient","type":"address"},{"name":"deadline","type":"uint256"},{"name":"amountIn","type":"uint256"},{"name":"amountOutMinimum","type":"uint256"},{"name":"sqrtPriceLimitX96","type":"uint160"}],"name":"params","type":"tuple"}],"name":"exactInputSingle","outputs":[{"name":"amountOut","type":"uint256"}],"stateMutability":"payable","type":"function"}]')

w3 = Web3(Web3.HTTPProvider(RPC))
account = Account.from_key(PK)
wallet = account.address
print(f"Wallet: {wallet}")

usdc_native = w3.eth.contract(address=w3.to_checksum_address(USDC_NATIVE), abi=ERC20_ABI)
usdc_e = w3.eth.contract(address=w3.to_checksum_address(USDC_E), abi=ERC20_ABI)

# Check balances
native_bal = usdc_native.functions.balanceOf(w3.to_checksum_address(wallet)).call()
bridged_bal = usdc_e.functions.balanceOf(w3.to_checksum_address(wallet)).call()
pol_bal = w3.eth.get_balance(w3.to_checksum_address(wallet))

print(f"\n=== BEFORE ===")
print(f"USDC native: {native_bal / 1e6:.4f}")
print(f"USDC.e: {bridged_bal / 1e6:.4f}")
print(f"POL: {float(w3.from_wei(pol_bal, 'ether')):.4f}")

def send_tx(tx_dict):
    """Sign and send a transaction, return receipt."""
    tx_dict["nonce"] = w3.eth.get_transaction_count(w3.to_checksum_address(wallet))
    tx_dict["from"] = w3.to_checksum_address(wallet)
    tx_dict["chainId"] = 137
    
    # Estimate gas
    if "gas" not in tx_dict:
        try:
            gas_est = w3.eth.estimate_gas(tx_dict)
            tx_dict["gas"] = int(gas_est * 1.3)
        except Exception as e:
            print(f"  Gas estimate failed: {e}")
            tx_dict["gas"] = 300000
    
    # Get gas price
    gas_price = w3.eth.gas_price
    tx_dict["gasPrice"] = int(gas_price * 1.2)
    
    signed = account.sign_transaction(tx_dict)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"  TX: {tx_hash.hex()}")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    print(f"  Status: {'SUCCESS' if receipt.status == 1 else 'FAILED'}")
    return receipt

if native_bal > 0:
    print(f"\n=== STEP 1: Approve USDC native to Uniswap Router ===")
    allowance = usdc_native.functions.allowance(
        w3.to_checksum_address(wallet),
        w3.to_checksum_address(SWAP_ROUTER)
    ).call()
    
    if allowance < native_bal:
        tx = usdc_native.functions.approve(
            w3.to_checksum_address(SWAP_ROUTER),
            MAX_UINT256
        ).build_transaction({})
        receipt = send_tx(tx)
        if receipt.status != 1:
            print("FAILED to approve! Exiting.")
            sys.exit(1)
        print("  Approved!")
    else:
        print("  Already approved")

    print(f"\n=== STEP 2: Swap USDC native -> USDC.e via Uniswap V3 ===")
    swap_amount = native_bal  # All of it
    min_out = int(swap_amount * 0.995)  # 0.5% slippage max
    deadline = int(time.time()) + 600  # 10 minutes
    
    router = w3.eth.contract(address=w3.to_checksum_address(SWAP_ROUTER), abi=SWAP_ABI)
    
    # Try 0.01% fee tier first (stablecoin pairs), then 0.05%
    for fee_tier in [100, 500, 3000]:
        print(f"  Trying fee tier: {fee_tier/10000}%...")
        try:
            params = (
                w3.to_checksum_address(USDC_NATIVE),   # tokenIn
                w3.to_checksum_address(USDC_E),         # tokenOut
                fee_tier,                                # fee
                w3.to_checksum_address(wallet),          # recipient
                deadline,                                # deadline
                swap_amount,                             # amountIn
                min_out,                                 # amountOutMinimum
                0,                                       # sqrtPriceLimitX96
            )
            tx = router.functions.exactInputSingle(params).build_transaction({
                "value": 0,
            })
            receipt = send_tx(tx)
            if receipt.status == 1:
                print(f"  SWAP SUCCESS! Fee tier: {fee_tier/10000}%")
                break
            else:
                print(f"  Swap failed at fee tier {fee_tier}")
        except Exception as e:
            print(f"  Fee tier {fee_tier} failed: {str(e)[:100]}")
            continue
    else:
        print("  WARNING: All swap attempts failed!")
        print("  You may need to swap manually in MetaMask: USDC -> USDC.e")
        # Continue anyway to set approvals

# Check balance after swap
time.sleep(3)
bridged_bal = usdc_e.functions.balanceOf(w3.to_checksum_address(wallet)).call()
native_bal = usdc_native.functions.balanceOf(w3.to_checksum_address(wallet)).call()
print(f"\n=== AFTER SWAP ===")
print(f"USDC native: {native_bal / 1e6:.4f}")
print(f"USDC.e: {bridged_bal / 1e6:.4f}")

# STEP 3: Approve USDC.e to Polymarket contracts
print(f"\n=== STEP 3: Approve USDC.e to Polymarket contracts ===")
contracts_to_approve = [
    ("CTF", CTF),
    ("CTF_EXCHANGE", CTF_EXCHANGE),
    ("NEG_RISK_CTF_EXCHANGE", NEG_RISK_CTF_EXCHANGE),
    ("NEG_RISK_ADAPTER", NEG_RISK_ADAPTER),
]

for name, addr in contracts_to_approve:
    allowance = usdc_e.functions.allowance(
        w3.to_checksum_address(wallet),
        w3.to_checksum_address(addr)
    ).call()
    
    if allowance > 0:
        print(f"  {name}: already approved ({allowance})")
        continue
    
    print(f"  Approving {name} ({addr[:10]}...)...")
    tx = usdc_e.functions.approve(
        w3.to_checksum_address(addr),
        MAX_UINT256
    ).build_transaction({})
    receipt = send_tx(tx)
    if receipt.status == 1:
        print(f"  {name}: APPROVED!")
    else:
        print(f"  {name}: FAILED!")

# STEP 4: Also approve CTF token (ERC-1155) for the exchanges
print(f"\n=== STEP 4: Approve CTF token (ERC-1155) to exchanges ===")
ERC1155_ABI = json.loads('[{"inputs":[{"name":"operator","type":"address"},{"name":"approved","type":"bool"}],"name":"setApprovalForAll","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"name":"account","type":"address"},{"name":"operator","type":"address"}],"name":"isApprovedForAll","outputs":[{"name":"","type":"bool"}],"stateMutability":"view","type":"function"}]')

ctf_contract = w3.eth.contract(address=w3.to_checksum_address(CTF), abi=ERC1155_ABI)

for name, addr in [("CTF_EXCHANGE", CTF_EXCHANGE), ("NEG_RISK_CTF_EXCHANGE", NEG_RISK_CTF_EXCHANGE)]:
    approved = ctf_contract.functions.isApprovedForAll(
        w3.to_checksum_address(wallet),
        w3.to_checksum_address(addr)
    ).call()
    
    if approved:
        print(f"  CTF -> {name}: already approved")
        continue
    
    print(f"  Approving CTF -> {name}...")
    tx = ctf_contract.functions.setApprovalForAll(
        w3.to_checksum_address(addr),
        True
    ).build_transaction({})
    receipt = send_tx(tx)
    if receipt.status == 1:
        print(f"  CTF -> {name}: APPROVED!")
    else:
        print(f"  CTF -> {name}: FAILED!")

# Final balance check
print(f"\n{'='*50}")
print(f"FINAL STATUS")
print(f"{'='*50}")
bridged_bal = usdc_e.functions.balanceOf(w3.to_checksum_address(wallet)).call()
native_bal = usdc_native.functions.balanceOf(w3.to_checksum_address(wallet)).call()
pol_bal = w3.eth.get_balance(w3.to_checksum_address(wallet))
print(f"USDC.e: ${bridged_bal / 1e6:.2f}")
print(f"USDC native: ${native_bal / 1e6:.2f}")
print(f"POL: {float(w3.from_wei(pol_bal, 'ether')):.4f}")

# Check all approvals
for name, addr in contracts_to_approve:
    allowance = usdc_e.functions.allowance(
        w3.to_checksum_address(wallet),
        w3.to_checksum_address(addr)
    ).call()
    status = "OK" if allowance > 0 else "MISSING"
    print(f"USDC.e -> {name}: {status}")

for name, addr in [("CTF_EXCHANGE", CTF_EXCHANGE), ("NEG_RISK_CTF_EXCHANGE", NEG_RISK_CTF_EXCHANGE)]:
    approved = ctf_contract.functions.isApprovedForAll(
        w3.to_checksum_address(wallet),
        w3.to_checksum_address(addr)
    ).call()
    status = "OK" if approved else "MISSING"
    print(f"CTF -> {name}: {status}")

print(f"\nREADY TO TRADE: {bridged_bal > 0}")
'''

# Upload script to VPS
print("Uploading setup script to VPS...")
sftp = ssh.open_sftp()
with sftp.file("/root/polyclaw-bot/complete_setup.py", "w") as f:
    f.write(setup_script)
sftp.close()
print("Uploaded!\n")

# Run the script
print("=" * 60)
print("RUNNING COMPLETE SETUP (swap + approvals)...")
print("=" * 60)
out, err = run("cd /root/polyclaw-bot && /root/.local/bin/uv run python complete_setup.py", timeout=300)
print(out)
if err:
    # Filter out warnings
    for line in err.split("\n"):
        if "Error" in line or "error" in line or "FAIL" in line or "Traceback" in line:
            print("ERR:", line)

ssh.close()
print("\nDONE!")
