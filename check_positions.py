"""
Check our current positions - when do they resolve and what's the expected P&L?
"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from lib.gamma_client import GammaClient

async def main():
    gamma = GammaClient()
    
    print("="*65)
    print("  📊 YOUR CURRENT POLYMARKET POSITIONS")
    print("="*65)
    
    # Our known positions from the audit
    positions = [
        {
            "name": "Fed Rates: Decrease 50+ bps YES",
            "search": "Fed interest rate decrease 50",
            "shares": 166.67 + 181.82,  # two runs
            "avg_price": 0.0065,
            "side": "YES",
        },
        {
            "name": "Fed Rates: Increase 25+ bps YES", 
            "search": "Fed interest rate increase 25",
            "shares": 166.67 + 181.82,
            "avg_price": 0.0055,
            "side": "YES",
        },
        {
            "name": "Fed No Change YES",
            "search": "Fed interest rate no change",
            "shares": 2.15,
            "avg_price": 0.93,
            "side": "YES",
        },
        {
            "name": "Bitcoin < $80K NO",
            "search": "Bitcoin below 80000",
            "shares": 2.19,
            "avg_price": 0.89,
            "side": "NO",
        },
    ]
    
    total_spent = 0
    total_current_value = 0
    
    for pos in positions:
        cost = pos["shares"] * pos["avg_price"]
        total_spent += cost
        
        # Try to find current market price
        try:
            markets = await gamma.search_markets(pos["search"], limit=3)
            if markets:
                m = markets[0]
                current_price = m.yes_price if pos["side"] == "YES" else m.no_price
                current_value = pos["shares"] * current_price
                total_current_value += current_value
                pnl = current_value - cost
                
                # Resolution info
                end_date = m.end_date or "unknown"
                resolved = "✅ RESOLVED" if m.resolved else "⏳ PENDING"
                closed = " (CLOSED)" if m.closed else ""
                
                print(f"\n  📌 {pos['name']}")
                print(f"     Shares: {pos['shares']:.2f} @ ${pos['avg_price']:.4f} = ${cost:.2f} spent")
                print(f"     Current price: ${current_price:.4f}")
                print(f"     Current value: ${current_value:.2f}")
                print(f"     P&L: {'🟢' if pnl >= 0 else '🔴'} ${pnl:+.2f}")
                print(f"     Status: {resolved}{closed}")
                print(f"     End date: {end_date}")
                print(f"     Market: {m.question[:70]}")
            else:
                print(f"\n  📌 {pos['name']}")
                print(f"     Shares: {pos['shares']:.2f} @ ${pos['avg_price']:.4f} = ${cost:.2f}")
                print(f"     ⚠️ Market not found in search")
        except Exception as e:
            print(f"\n  📌 {pos['name']}")
            print(f"     Error: {e}")
    
    print(f"\n{'='*65}")
    print(f"  💰 TOTAL SPENT: ${total_spent:.2f}")
    print(f"  💵 CURRENT VALUE: ${total_current_value:.2f}")
    print(f"  📈 TOTAL P&L: ${total_current_value - total_spent:+.2f}")
    print(f"  🏦 POLYMARKET COLLATERAL: ~$19.79")
    print(f"  💎 TOTAL ACCOUNT VALUE: ~${total_current_value + 19.79:.2f}")
    print(f"{'='*65}")

asyncio.run(main())
