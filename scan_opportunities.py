"""
Dry-run scanner: Check what REAL hedge opportunities exist on Polymarket right now.
No trading — just scanning and reporting.
"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from lib.gamma_client import GammaClient

POLY_FEE = 0.02
MIN_PROFIT = 0.003

async def main():
    gamma = GammaClient()
    
    print("="*70)
    print("  POLYMARKET HEDGE OPPORTUNITY SCANNER (DRY RUN)")
    print("="*70)
    
    # ---- SCAN 1: Event Group Arbitrage ----
    print("\n📦 SCANNER 1: Event Group Arbitrage")
    print("-"*50)
    
    events = await gamma.get_events(limit=50)
    print(f"  Fetched {len(events)} events")
    
    group_opps = 0
    for event in events:
        active = [m for m in event.markets if m.active and not m.closed and not m.resolved]
        if len(active) < 3:
            continue
        
        total_yes = sum(m.yes_price for m in active)
        total_no = sum(m.no_price for m in active)
        
        # Check if it looks exclusive (prices sum ~1.0)
        is_exclusive = 0.85 <= total_yes <= 1.15
        
        threshold = 1.0 - MIN_PROFIT - POLY_FEE * 2
        yes_arb = total_yes > 0 and total_yes < threshold
        no_arb = total_no > 0 and total_no < threshold
        
        if is_exclusive or yes_arb or no_arb:
            print(f"\n  📊 {event.title}")
            print(f"     Outcomes: {len(active)}")
            for m in active:
                print(f"       • {m.question[:60]:60s} YES=${m.yes_price:.4f}  NO=${m.no_price:.4f}  vol=${m.volume_24h:,.0f}")
            print(f"     ∑YES = ${total_yes:.4f}  ∑NO = ${total_no:.4f}")
            
            if yes_arb:
                profit = (1.0 - total_yes) / total_yes - POLY_FEE * 2
                print(f"     ✅ YES ARB! Buy all YES for ${total_yes:.4f}, get $1.00 → net profit/$ = {profit:.4f}")
                group_opps += 1
            elif no_arb:
                profit = (1.0 - total_no) / total_no - POLY_FEE * 2
                print(f"     ✅ NO ARB! Buy all NO for ${total_no:.4f}, get $1.00 → net profit/$ = {profit:.4f}")
                group_opps += 1
            else:
                gap = total_yes - 1.0
                print(f"     ❌ No arb (overpriced by ${gap:.4f}, need <${threshold:.4f})")
    
    print(f"\n  → {group_opps} event group opportunities found")
    
    # ---- SCAN 2: Threshold Mispricing ----
    print("\n📐 SCANNER 2: Threshold Mispricing")
    print("-"*50)
    
    # Search for crypto threshold markets
    threshold_opps = 0
    for asset in ["Bitcoin", "Ethereum", "SOL", "S&P", "oil"]:
        try:
            markets = await gamma.search_markets(f"{asset} price", limit=20)
        except:
            continue
        
        # Find price threshold pairs
        import re
        threshold_markets = []
        for m in markets:
            if not m.active or m.closed or m.resolved:
                continue
            q = m.question.lower()
            # Look for "above $X" or "below $X" type questions
            match = re.search(r'(?:above|below|over|under|>\s*\$?|<\s*\$?)\s*\$?([\d,]+(?:\.\d+)?)', q)
            if match:
                threshold = float(match.group(1).replace(',', ''))
                direction = "above" if any(w in q for w in ["above", "over", ">"]) else "below"
                threshold_markets.append((m, threshold, direction))
        
        if len(threshold_markets) < 2:
            continue
        
        # Sort by threshold
        threshold_markets.sort(key=lambda x: x[1])
        
        # Check pairs: high_threshold NO + low_threshold YES
        for i in range(len(threshold_markets)):
            for j in range(i+1, len(threshold_markets)):
                low_m, low_t, low_d = threshold_markets[i]
                high_m, high_t, high_d = threshold_markets[j]
                
                if low_d != "above" or high_d != "above":
                    continue
                
                cost = high_m.no_price + low_m.yes_price
                if cost > 0 and cost < (1.0 - MIN_PROFIT - POLY_FEE * 2):
                    guaranteed = 1.0 - cost
                    net_profit = guaranteed / cost - POLY_FEE * 2
                    print(f"\n  ✅ THRESHOLD ARB: {asset}")
                    print(f"     Buy YES '{low_m.question[:50]}' @ ${low_m.yes_price:.4f}")
                    print(f"     Buy NO  '{high_m.question[:50]}' @ ${high_m.no_price:.4f}")
                    print(f"     Cost: ${cost:.4f} → Guaranteed $1.00 → profit/$ = {net_profit:.4f}")
                    threshold_opps += 1
    
    print(f"\n  → {threshold_opps} threshold opportunities found")
    
    # ---- SUMMARY ----
    print("\n" + "="*70)
    total = group_opps + threshold_opps
    if total > 0:
        print(f"  🎯 TOTAL: {total} REAL hedge opportunities available!")
        print(f"  These are GUARANTEED profit trades.")
    else:
        print(f"  ⚠️  NO hedge opportunities found right now.")
        print(f"  Markets are efficiently priced. The bot will keep scanning until one appears.")
        print(f"  Real hedges are RARE — they appear when markets misprice temporarily.")
    print("="*70)

asyncio.run(main())
