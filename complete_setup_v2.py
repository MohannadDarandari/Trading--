"""
COMPLETE SETUP v2: Swap USDC native -> USDC.e + Set Polymarket approvals.
Fixed: include 'from' in build_transaction
"""
import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("172.233.220.24", username="root", password="MOHANNAD@1011")

def run(cmd, timeout=300):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode(), stderr.read().decode()

setup_script = r'''
import json, time, sys
from web3 import Web3
from eth_account import Account

RPC = "https://polygon-mainnet.g.alchemy.com/v2/S9mnnjfuSy_gDGll0If76"
PK = "33b0c6d92c974489686742b4af56e168530a3f1d794a3c2c23831c59d8a369e9"

USDC_NATIVE = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"
USDC_E = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
CTF = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
CTF_EXCHANGE = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
NEG_RISK_CTF_EXCHANGE = "0xC5d563A36AE78145C45a50134d48A1215220f80a"
NEG_RISK_ADAPTER = "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296"
SWAP_ROUTER = "0xE592427A0AEce92De3Edee1F18E0157C05861564"
MAX_UINT256 = 2**256 - 1

ERC20_ABI = json.loads('[{"inputs":[{"name":"spender","type":"address"},{"name":"amount","type":"uint256"}],"name":"approve","outputs":[{"name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"name":"owner","type":"address"},{"name":"spender","type":"address"}],"name":"allowance","outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"name":"account","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"}]')
SWAP_ABI = json.loads('[{"inputs":[{"components":[{"name":"tokenIn","type":"address"},{"name":"tokenOut","type":"address"},{"name":"fee","type":"uint24"},{"name":"recipient","type":"address"},{"name":"deadline","type":"uint256"},{"name":"amountIn","type":"uint256"},{"name":"amountOutMinimum","type":"uint256"},{"name":"sqrtPriceLimitX96","type":"uint160"}],"name":"params","type":"tuple"}],"name":"exactInputSingle","outputs":[{"name":"amountOut","type":"uint256"}],"stateMutability":"payable","type":"function"}]')
ERC1155_ABI = json.loads('[{"inputs":[{"name":"operator","type":"address"},{"name":"approved","type":"bool"}],"name":"setApprovalForAll","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"name":"account","type":"address"},{"name":"operator","type":"address"}],"name":"isApprovedForAll","outputs":[{"name":"","type":"bool"}],"stateMutability":"view","type":"function"}]')

w3 = Web3(Web3.HTTPProvider(RPC))
account = Account.from_key(PK)
wallet = w3.to_checksum_address(account.address)
print(f"Wallet: {wallet}")
nonce = w3.eth.get_transaction_count(wallet)

usdc_native = w3.eth.contract(address=w3.to_checksum_address(USDC_NATIVE), abi=ERC20_ABI)
usdc_e = w3.eth.contract(address=w3.to_checksum_address(USDC_E), abi=ERC20_ABI)

native_bal = usdc_native.functions.balanceOf(wallet).call()
bridged_bal = usdc_e.functions.balanceOf(wallet).call()
pol_bal = w3.eth.get_balance(wallet)
print(f"\n=== BEFORE ===")
print(f"USDC native: {native_bal / 1e6:.4f}")
print(f"USDC.e: {bridged_bal / 1e6:.4f}")
print(f"POL: {float(w3.from_wei(pol_bal, 'ether')):.4f}")

def send_tx(func, value=0):
    global nonce
    gas_price = int(w3.eth.gas_price * 1.2)
    tx = func.build_transaction({
        "from": wallet,
        "nonce": nonce,
        "chainId": 137,
        "value": value,
        "gasPrice": gas_price,
    })
    try:
        gas = w3.eth.estimate_gas(tx)
        tx["gas"] = int(gas * 1.3)
    except Exception as e:
        print(f"  Gas estimate failed: {e}")
        tx["gas"] = 300000
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"  TX: {tx_hash.hex()}")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    status = "SUCCESS" if receipt.status == 1 else "FAILED"
    print(f"  Status: {status} | Gas used: {receipt.gasUsed}")
    nonce += 1
    return receipt

# === STEP 1: Approve USDC native to Uniswap Router ===
if native_bal > 0:
    print(f"\n=== STEP 1: Approve USDC native -> Uniswap Router ===")
    allowance = usdc_native.functions.allowance(wallet, w3.to_checksum_address(SWAP_ROUTER)).call()
    if allowance < native_bal:
        func = usdc_native.functions.approve(w3.to_checksum_address(SWAP_ROUTER), MAX_UINT256)
        r = send_tx(func)
        if r.status != 1:
            print("FAILED! Exiting.")
            sys.exit(1)
        print("  Approved!")
    else:
        print("  Already approved")

    # === STEP 2: Swap USDC native -> USDC.e ===
    print(f"\n=== STEP 2: Swap {native_bal/1e6:.4f} USDC native -> USDC.e ===")
    router = w3.eth.contract(address=w3.to_checksum_address(SWAP_ROUTER), abi=SWAP_ABI)
    min_out = int(native_bal * 0.99)  # 1% slippage
    deadline = int(time.time()) + 600

    swapped = False
    for fee_tier in [100, 500, 3000]:
        print(f"  Trying fee tier {fee_tier} ({fee_tier/10000}%)...")
        try:
            params = (
                w3.to_checksum_address(USDC_NATIVE),
                w3.to_checksum_address(USDC_E),
                fee_tier,
                wallet,
                deadline,
                native_bal,
                min_out,
                0,
            )
            func = router.functions.exactInputSingle(params)
            r = send_tx(func)
            if r.status == 1:
                print(f"  SWAP SUCCESS!")
                swapped = True
                break
            else:
                print(f"  Swap reverted at fee {fee_tier}")
        except Exception as e:
            err_msg = str(e)[:150]
            print(f"  Failed: {err_msg}")
            continue

    if not swapped:
        print("\n  WARNING: Uniswap swap failed. Trying alternative...")
        print("  User needs to swap manually in MetaMask:")
        print("  USDC -> USDC.e (address: 0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174)")

# Check balance after swap
time.sleep(3)
bridged_bal = usdc_e.functions.balanceOf(wallet).call()
native_bal = usdc_native.functions.balanceOf(wallet).call()
print(f"\n=== AFTER SWAP ===")
print(f"USDC native: {native_bal / 1e6:.4f}")
print(f"USDC.e: {bridged_bal / 1e6:.4f}")

# === STEP 3: Approve USDC.e to Polymarket ===
if bridged_bal > 0:
    print(f"\n=== STEP 3: Approve USDC.e -> Polymarket contracts ===")
    for name, addr in [("CTF", CTF), ("CTF_EXCHANGE", CTF_EXCHANGE), ("NEG_RISK_CTF_EXCHANGE", NEG_RISK_CTF_EXCHANGE), ("NEG_RISK_ADAPTER", NEG_RISK_ADAPTER)]:
        allowance = usdc_e.functions.allowance(wallet, w3.to_checksum_address(addr)).call()
        if allowance > 0:
            print(f"  {name}: already approved")
            continue
        print(f"  Approving USDC.e -> {name}...")
        func = usdc_e.functions.approve(w3.to_checksum_address(addr), MAX_UINT256)
        r = send_tx(func)
        print(f"  {name}: {'DONE' if r.status==1 else 'FAILED'}")

    # === STEP 4: Approve CTF (ERC-1155) ===
    print(f"\n=== STEP 4: Approve CTF (ERC-1155) -> Exchanges ===")
    ctf = w3.eth.contract(address=w3.to_checksum_address(CTF), abi=ERC1155_ABI)
    for name, addr in [("CTF_EXCHANGE", CTF_EXCHANGE), ("NEG_RISK_CTF_EXCHANGE", NEG_RISK_CTF_EXCHANGE)]:
        approved = ctf.functions.isApprovedForAll(wallet, w3.to_checksum_address(addr)).call()
        if approved:
            print(f"  CTF -> {name}: already approved")
            continue
        print(f"  Approving CTF -> {name}...")
        func = ctf.functions.setApprovalForAll(w3.to_checksum_address(addr), True)
        r = send_tx(func)
        print(f"  CTF -> {name}: {'DONE' if r.status==1 else 'FAILED'}")
else:
    print("\nNo USDC.e balance - skipping approvals")
    print("User must swap USDC native to USDC.e first!")

# === FINAL STATUS ===
print(f"\n{'='*50}")
print("FINAL STATUS")
print(f"{'='*50}")
bridged_bal = usdc_e.functions.balanceOf(wallet).call()
native_bal = usdc_native.functions.balanceOf(wallet).call()
pol_bal = w3.eth.get_balance(wallet)
print(f"USDC.e: ${bridged_bal / 1e6:.2f} (trading balance)")
print(f"USDC native: ${native_bal / 1e6:.2f}")
print(f"POL: {float(w3.from_wei(pol_bal, 'ether')):.4f}")
print(f"\nApprovals:")
for name, addr in [("CTF", CTF), ("CTF_EXCHANGE", CTF_EXCHANGE), ("NEG_RISK_CTF_EXCHANGE", NEG_RISK_CTF_EXCHANGE), ("NEG_RISK_ADAPTER", NEG_RISK_ADAPTER)]:
    a = usdc_e.functions.allowance(wallet, w3.to_checksum_address(addr)).call()
    print(f"  USDC.e -> {name}: {'OK' if a > 0 else 'MISSING'}")
ctf = w3.eth.contract(address=w3.to_checksum_address(CTF), abi=ERC1155_ABI)
for name, addr in [("CTF_EXCHANGE", CTF_EXCHANGE), ("NEG_RISK_CTF_EXCHANGE", NEG_RISK_CTF_EXCHANGE)]:
    a = ctf.functions.isApprovedForAll(wallet, w3.to_checksum_address(addr)).call()
    print(f"  CTF -> {name}: {'OK' if a else 'MISSING'}")
print(f"\nREADY_TO_TRADE: {bridged_bal > 0}")
'''

print("Uploading fixed setup script...")
sftp = ssh.open_sftp()
with sftp.file("/root/polyclaw-bot/complete_setup.py", "w") as f:
    f.write(setup_script)
sftp.close()

print("Running complete setup (swap + approvals)...\n")
out, err = run("cd /root/polyclaw-bot && /root/.local/bin/uv run python complete_setup.py", timeout=300)
print(out)
if err:
    important = [l for l in err.split("\n") if any(k in l for k in ["Error", "error", "FAIL", "Traceback", "raise"])]
    if important:
        print("ERRORS:")
        for l in important[-10:]:
            print(f"  {l}")

ssh.close()
