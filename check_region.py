"""Check VPS region and set up geo-unblock solution."""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("172.233.220.24", username="root", password="MOHANNAD@1011")

def run(cmd, timeout=60):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode(), stderr.read().decode()

# 1. Check VPS region
print("=== VPS REGION CHECK ===")
out, _ = run("curl -s http://ip-api.com/json")
print(out)

# 2. Check if we can reach Polymarket from non-US
print("\n=== POLYMARKET API CHECK ===")
out, _ = run("curl -s -o /dev/null -w '%{http_code}' https://clob.polymarket.com/")
print(f"CLOB API status: {out}")

# 3. Check current proxy env
out, _ = run("env | grep -i proxy")
print(f"Proxy env: {out or 'NONE'}")

ssh.close()
