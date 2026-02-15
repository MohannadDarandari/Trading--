"""
Find our exact positions by searching with different terms.
"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from lib.gamma_client import GammaClient

async def main():
    gamma = GammaClient()
    
    searches = [
        "fed funds rate",
        "interest rate decrease",
        "interest rate increase", 
        "interest rate no change",
        "federal reserve rate",
        "FOMC rate",
        "bitcoin 80000",
        "bitcoin 80k",
        "BTC 80000",
        "fed rate cut",
        "fed rate hike",
    ]
    
    seen = set()
    for s in searches:
        try:
            markets = await gamma.search_markets(s, limit=5)
            for m in markets:
                if m.id not in seen:
                    seen.add(m.id)
                    status = "RESOLVED" if m.resolved else "CLOSED" if m.closed else "ACTIVE"
                    print(f"  [{status}] {m.question[:80]}")
                    print(f"    YES=${m.yes_price:.4f}  NO=${m.no_price:.4f}  end={m.end_date or '?'}")
                    print(f"    ID: {m.id}")
                    print()
        except Exception as e:
            print(f"  Search '{s}' error: {e}")

asyncio.run(main())
