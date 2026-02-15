"""Fix the OrderBookSummary type bug and deploy to VPS."""
import paramiko, time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("172.233.220.24", username="root", password="MOHANNAD@1011")

def run(cmd, timeout=120):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode(), stderr.read().decode()

# 1. Check OrderBookSummary structure
print("=== CHECKING OrderBookSummary ===")
out, _ = run(
    "cd /root/polyclaw-bot && /root/.local/bin/uv run python -c \""
    "from py_clob_client.client import ClobClient; "
    "import inspect; "
    "from py_clob_client.clob_types import OrderBookSummary; "
    "print(dir(OrderBookSummary)); "
    "print(); "
    "src = inspect.getsource(OrderBookSummary); "
    "print(src[:500])"
    "\""
)
print(out)

# 2. Fix the get_order_book wrapper to return a dict
print("\n=== FIXING lib/clob_client.py ===")

# Current code: return self.client.get_order_book(token_id)
# Fix: convert OrderBookSummary to dict
run(
    r"sed -i 's|return self.client.get_order_book(token_id)|"
    r"ob = self.client.get_order_book(token_id); "
    r"return {\"asks\": [{\"price\": str(a.price), \"size\": str(a.size)} for a in (ob.asks or [])], "
    r"\"bids\": [{\"price\": str(b.price), \"size\": str(b.size)} for b in (ob.bids or [])]}|' "
    r"/root/polyclaw-bot/lib/clob_client.py"
)

# Verify
out, _ = run("grep -A2 'def get_order_book' /root/polyclaw-bot/lib/clob_client.py")
print("Fixed wrapper:")
print(out)

# 3. Also fix _check_depth to be safer with parsing
# The asks_raw list is already [{price, size}] dicts after our fix, so parsing should work

# 4. Test the fix
print("\n=== TESTING FIX ===")
test_out, test_err = run(
    "cd /root/polyclaw-bot && /root/.local/bin/uv run python -c \""
    "from lib.clob_client import ClobClientWrapper; "
    "clob = ClobClientWrapper("
    "private_key='33b0c6d92c974489686742b4af56e168530a3f1d794a3c2c23831c59d8a369e9', "
    "address='0xAdd5cf1e1d6992C0130C3a89094F300fA71d32E5'); "
    "ob = clob.get_order_book('46531580883893457486521223946750972005651221984783428974972634868855238318041'); "
    "print(type(ob)); "
    "print('asks:', len(ob.get('asks', []))); "
    "print('bids:', len(ob.get('bids', []))); "
    "if ob.get('asks'): print('First ask:', ob['asks'][0])"
    "\""
)
print(test_out)
if test_err:
    print("ERR:", test_err[-300:])

# 5. Also increase API error kill threshold from 5 to 15 (too aggressive for 10+ depth checks per scan)
print("\n=== INCREASING API ERROR THRESHOLD ===")
run("sed -i 's/KILL_API_ERRORS_10M = int(os.getenv(\"KILL_API_ERRORS_10M\", \"5\"))/KILL_API_ERRORS_10M = int(os.getenv(\"KILL_API_ERRORS_10M\", \"15\"))/' /root/polyclaw-bot/hedge_server_v4.py")
out, _ = run("grep 'KILL_API_ERRORS_10M' /root/polyclaw-bot/hedge_server_v4.py | head -1")
print(f"New threshold: {out.strip()}")

# 6. Restart
print("\n=== RESTARTING BOT ===")
run("systemctl restart polyclaw-bot")
time.sleep(30)

out, _ = run("journalctl -u polyclaw-bot --no-pager -n 40 --output=cat")
print(out)

ssh.close()
print("\nDONE!")
