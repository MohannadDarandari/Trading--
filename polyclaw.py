#!/usr/bin/env python3
"""
=== PolyClaw Quick Launcher ===
Run PolyClaw commands from your Trading$$ workspace.
"""
import subprocess
import sys
import os

POLYCLAW_DIR = os.path.expanduser("~\\.openclaw\\skills\\polyclaw")
UV_PATH = os.path.expanduser("~\\.local\\bin\\uv.exe")

def run_polyclaw(args):
    """Run a PolyClaw command."""
    cmd = [UV_PATH, "run", "python", "scripts/polyclaw.py"] + args
    result = subprocess.run(cmd, cwd=POLYCLAW_DIR, capture_output=False)
    return result.returncode

def main():
    if len(sys.argv) < 2:
        print("""
╔══════════════════════════════════════════════════════╗
║              🦞 PolyClaw Quick Launcher              ║
╠══════════════════════════════════════════════════════╣
║                                                      ║
║  MARKET COMMANDS:                                    ║
║    py polyclaw.py markets trending                   ║
║    py polyclaw.py markets search "election"          ║
║    py polyclaw.py market <market_id>                 ║
║                                                      ║
║  WALLET COMMANDS:                                    ║
║    py polyclaw.py wallet status                      ║
║    py polyclaw.py wallet approve  (one-time setup)   ║
║                                                      ║
║  TRADING COMMANDS:                                   ║
║    py polyclaw.py buy <market_id> YES 50             ║
║    py polyclaw.py buy <market_id> NO 25              ║
║    py polyclaw.py positions                          ║
║                                                      ║
║  HEDGE DISCOVERY (needs OpenRouter key):             ║
║    py polyclaw.py hedge scan                         ║
║    py polyclaw.py hedge scan --query "election"      ║
║    py polyclaw.py hedge analyze <id1> <id2>          ║
║                                                      ║
║  HEDGE TIERS:                                        ║
║    T1 >= 95%  = Near-Arbitrage (SAFEST)              ║
║    T2 90-95%  = Strong Hedge                         ║
║    T3 85-90%  = Decent Hedge                         ║
║                                                      ║
╚══════════════════════════════════════════════════════╝
""")
        return

    return run_polyclaw(sys.argv[1:])

if __name__ == "__main__":
    sys.exit(main() or 0)
