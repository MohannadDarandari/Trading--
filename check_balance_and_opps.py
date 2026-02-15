"""
Check Polymarket balance + find guaranteed hedges we can trade NOW.
Uses the CLOB API to check available balance on Polymarket exchange.
"""
import asyncio, sys, os, json
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from lib.gamma_client import GammaClient

POLY_FEE = 0.02
MIN_PROFIT = 0.003

async def main():
    pk = os.getenv("POLYCLAW_PRIVATE_KEY")
    if not pk:
        print("ERROR: POLYCLAW_PRIVATE_KEY not in .env")
        return
    
    # Check Polymarket CLOB balance
    print("="*60)
    print("  CHECKING POLYMARKET BALANCE & OPPORTUNITIES")
    print("="*60)
    
    from py_clob_client.client import ClobClient
    
    client = ClobClient(
        "https://clob.polymarket.com",
        key=pk,
        chain_id=137,
        signature_type=0,
        funder="0xAdd5cf1e1d6992C0130C3a89094F300fA71d32E5",
    )
    creds = client.create_or_derive_api_creds()
    client.set_api_creds(creds)
    
    # Get balance info
    print("\n💰 POLYMARKET BALANCE:")
    try:
        # Try to get balance from CLOB
        import httpx
        host = "https://clob.polymarket.com"
        headers = client.create_level_2_headers()
        
        async with httpx.AsyncClient(timeout=10) as http:
            # Try balance endpoint
            resp = await http.get(
                f"{host}/balances",
                headers=headers
            )
            print(f"  Balance response ({resp.status_code}): {resp.text[:500]}")
    except Exception as e:
        print(f"  Balance check error: {e}")
    
    # Check open orders
    print("\n📋 OPEN ORDERS:")
    try:
        orders = client.get_orders()
        if not orders:
            print("  No open orders")
        else:
            for o in orders[:10]:
                print(f"  {o}")
    except Exception as e:
        print(f"  Orders error: {e}")
    
    # Now scan for REAL opportunities with the actual scanner
    print("\n" + "="*60)
    print("  SCANNING FOR GUARANTEED HEDGES")
    print("="*60)
    
    gamma = GammaClient()
    events = await gamma.get_events(limit=100)
    print(f"  Fetched {len(events)} events")
    
    opportunities = []
    
    for event in events:
        active = [m for m in event.markets if m.active and not m.closed and not m.resolved]
        if len(active) < 2:
            continue
        
        total_yes = sum(m.yes_price for m in active)
        total_no = sum(m.no_price for m in active)
        
        # Check exclusivity (sum ~ 1.0)
        if not (0.85 <= total_yes <= 1.15):
            continue
        
        threshold = 1.0 - MIN_PROFIT - POLY_FEE * 2
        
        # Strategy 1: Buy all YES 
        if total_yes > 0 and total_yes < threshold:
            profit_pct = ((1.0 - total_yes) / total_yes - POLY_FEE * 2) * 100
            if profit_pct > 0:
                # Calculate cost for minimum viable trade
                min_prices = [m.yes_price for m in active]
                min_price = min(min_prices)
                # Need at least 5 shares per leg, or $1 per leg
                shares_needed = max(5, 1.0 / min_price if min_price > 0 else 5)
                total_cost = shares_needed * total_yes
                
                opportunities.append({
                    "event": event.title,
                    "type": "BUY ALL YES",
                    "outcomes": len(active),
                    "total_yes": total_yes,
                    "profit_pct": profit_pct,
                    "min_cost": total_cost,
                    "markets": [(m.question[:50], m.yes_price, m.yes_token_id, m.volume_24h) for m in active],
                })
        
        # Strategy 2: Buy all NO
        if total_no > 0 and total_no < threshold:
            profit_pct = ((1.0 - total_no) / total_no - POLY_FEE * 2) * 100
            if profit_pct > 0:
                min_prices = [m.no_price for m in active]
                min_price = min(min_prices)
                shares_needed = max(5, 1.0 / min_price if min_price > 0 else 5)
                total_cost = shares_needed * total_no
                
                opportunities.append({
                    "event": event.title,
                    "type": "BUY ALL NO",
                    "outcomes": len(active),
                    "total_no": total_no,
                    "profit_pct": profit_pct,
                    "min_cost": total_cost,
                    "markets": [(m.question[:50], m.no_price, m.no_token_id or "", m.volume_24h) for m in active],
                })
    
    # Sort by profit %
    opportunities.sort(key=lambda x: x["profit_pct"], reverse=True)
    
    print(f"\n🎯 FOUND {len(opportunities)} GUARANTEED OPPORTUNITIES:\n")
    
    for i, opp in enumerate(opportunities, 1):
        print(f"  {i}. {opp['event'][:50]}")
        print(f"     Strategy: {opp['type']}")
        print(f"     Outcomes: {opp['outcomes']}")
        price_key = 'total_yes' if 'total_yes' in opp else 'total_no'
        print(f"     Total Price: ${opp.get(price_key, 0):.4f}")
        print(f"     PROFIT: {opp['profit_pct']:.2f}%")
        print(f"     Min Cost: ${opp['min_cost']:.2f}")
        
        # Show legs with volume info
        print(f"     Legs:")
        for q, price, token_id, vol in opp["markets"]:
            vol_str = f"vol=${vol:,.0f}" if vol else "vol=LOW"
            print(f"       • {q:50s} @ ${price:.4f}  {vol_str}")
        
        affordable = opp["min_cost"] <= 19.79
        print(f"     💵 Can afford with $19.79? {'✅ YES' if affordable else '❌ NO'}")
        print()
    
    if not opportunities:
        print("  ⚠️ No guaranteed arbitrage opportunities right now.")
        print("  Markets are efficiently priced. Bot needs to keep scanning.")

asyncio.run(main())
