"""Quick test: is London VPS blocked by Polymarket?"""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('172.236.9.220', username='root', password='MOHANNAD@1011', timeout=15)

print("="*50)
print("  🔍 LONDON VPS - POLYMARKET CONNECTIVITY TEST")
print("="*50)

# Test 1: Gamma API
stdin, stdout, stderr = ssh.exec_command(
    "python3 -c \"import httpx; r = httpx.get('https://gamma-api.polymarket.com/events?limit=1'); print(r.status_code)\"",
    timeout=15
)
stdout.channel.recv_exit_status()
gamma = stdout.read().decode().strip()
print(f"\n  Gamma API: {gamma} {'✅' if gamma == '200' else '❌ BLOCKED!'}")

# Test 2: CLOB API
stdin, stdout, stderr = ssh.exec_command(
    "python3 -c \"import httpx; r = httpx.get('https://clob.polymarket.com/time'); print(r.status_code)\"",
    timeout=15
)
stdout.channel.recv_exit_status()
clob = stdout.read().decode().strip()
print(f"  CLOB API:  {clob} {'✅' if clob == '200' else '❌ BLOCKED!'}")

# Test 3: Bot service
stdin, stdout, stderr = ssh.exec_command("systemctl is-active polyclaw", timeout=5)
status = stdout.read().decode().strip()
print(f"  Bot:       {status} {'✅' if status == 'active' else '❌'}")

# Test 4: Recent scan
stdin, stdout, stderr = ssh.exec_command(
    "journalctl -u polyclaw --no-pager -n 15 | grep -E 'Scanned|Found|ALERTED|error|403|block|profit'",
    timeout=10
)
stdout.channel.recv_exit_status()
logs = stdout.read().decode().strip()
if logs:
    print(f"\n  📜 Recent activity:")
    for line in logs.split('\n')[-8:]:
        msg = line.split(']: ', 1)[-1] if ']: ' in line else line
        print(f"    {msg[:120]}")

# Test 5: VPS IP location
stdin, stdout, stderr = ssh.exec_command(
    "python3 -c \"import httpx; r = httpx.get('https://ipinfo.io/json'); d = r.json(); print(f'{d.get(\"ip\")} | {d.get(\"city\")} | {d.get(\"country\")}')\"",
    timeout=10
)
stdout.channel.recv_exit_status()
ip_info = stdout.read().decode().strip()
print(f"\n  🌐 VPS Location: {ip_info}")

ssh.close()

if gamma == '200' and clob == '200':
    print("\n  ✅ لندن يشتغل! مو محظور!")
else:
    print("\n  ❌ لندن محظور!")
