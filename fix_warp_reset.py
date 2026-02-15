"""Reconnect to VPS and switch WARP back to proxy mode."""
import paramiko, time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

# Try to reconnect (WARP full tunnel might still allow SSH on the original IP)
for attempt in range(3):
    try:
        print(f"Attempt {attempt+1}: Connecting...")
        ssh.connect("172.236.9.220", username="root", password="MOHANNAD@1011", timeout=15)
        print("Connected!")
        
        # Immediately switch back to proxy mode
        stdin, stdout, stderr = ssh.exec_command("warp-cli --accept-tos disconnect; warp-cli --accept-tos mode proxy; warp-cli --accept-tos connect; echo DONE", timeout=30)
        out = stdout.read().decode()
        print(f"Output: {out}")
        
        # Verify
        stdin, stdout, stderr = ssh.exec_command("warp-cli --accept-tos status 2>&1", timeout=15)
        out = stdout.read().decode()
        print(f"Status: {out.strip()}")
        
        stdin, stdout, stderr = ssh.exec_command("ss -tlnp | grep 40000 2>&1", timeout=10)
        out = stdout.read().decode()
        print(f"Port 40000: {out.strip() or 'NOT LISTENING'}")
        
        break
    except Exception as e:
        print(f"  Failed: {e}")
        if attempt < 2:
            print(f"  Waiting 10s...")
            time.sleep(10)

ssh.close()
