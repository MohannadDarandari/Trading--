"""Analyze: is the Fed Rates trade actually a hedge? Show ALL outcomes."""
import os, json, requests
os.chdir(r"C:\Users\mdara\OneDrive\Desktop\DarkOps HQ\Trading$$")
from dotenv import load_dotenv
load_dotenv()

# 1. Find ALL Fed Rates outcomes for March 2026
print("=" * 60)
print("FED RATES MARCH 2026 — ALL OUTCOMES")
print("=" * 60)

# Search for the event
r = requests.get("https://gamma-api.polymarket.com/markets?limit=50&closed=false&tag=fed-rates")
markets = r.json()

# Also search by text
r2 = requests.get("https://gamma-api.polymarket.com/markets?limit=50&closed=false&active=true")
all_markets = r2.json()

fed_markets = [m for m in all_markets if 'fed' in m.get('question','').lower() and 'march' in m.get('question','').lower() and '2026' in m.get('question','').lower()]
if not fed_markets:
    fed_markets = [m for m in all_markets if 'interest rate' in m.get('question','').lower() or 'fed' in m.get('question','').lower()]

print(f"Found {len(fed_markets)} Fed markets")

# Get the event group using our known market IDs
for mid in ["654412", "654413", "654414", "654415", "654416"]:
    try:
        r = requests.get(f"https://gamma-api.polymarket.com/markets/{mid}")
        if r.ok:
            m = r.json()
            q = m.get('question', '')
            group = m.get('groupItemTitle', '')
            event_slug = m.get('eventSlug', '')
            cid = m.get('conditionId', '')[:30]
            outcome_prices = m.get('outcomePrices', '')
            print(f"  [{mid}] {q[:70]}")
            print(f"         group: {group} | event: {event_slug}")
            print(f"         prices: {outcome_prices}")
    except:
        pass

# Try to find all outcomes in same event group
print("\n" + "=" * 60)
print("FINDING EVENT GROUP")
print("=" * 60)

# Get event by slug
r = requests.get("https://gamma-api.polymarket.com/markets/654412")
if r.ok:
    m = r.json()
    event_slug = m.get('eventSlug', '')
    print(f"Event slug: {event_slug}")
    
    if event_slug:
        r2 = requests.get(f"https://gamma-api.polymarket.com/events?slug={event_slug}")
        events = r2.json()
        if events:
            event = events[0] if isinstance(events, list) else events
            print(f"Event: {event.get('title', '')}")
            event_markets = event.get('markets', [])
            print(f"Total outcomes: {len(event_markets)}")
            
            total_yes_price = 0
            print("\nALL outcomes:")
            for em in event_markets:
                prices = em.get('outcomePrices', '[]')
                try:
                    yes_price = float(json.loads(prices)[0]) if prices else 0
                except:
                    yes_price = 0
                total_yes_price += yes_price
                mid = em.get('id', '')
                title = em.get('groupItemTitle', em.get('question', ''))[:50]
                print(f"  [{mid}] {title}: YES=${yes_price:.4f}")
            
            print(f"\nTotal YES prices: ${total_yes_price:.4f}")
            print(f"Hedge cost per unit: ${total_yes_price:.4f}")
            if total_yes_price < 1.0:
                print(f"PROFIT per unit if hedged: ${1.0 - total_yes_price:.4f}")
            else:
                print(f"NO PROFIT — costs MORE than $1 to cover all outcomes!")

# 2. What WE actually bought
print("\n" + "=" * 60)
print("WHAT WE BOUGHT (NOT A HEDGE!)")
print("=" * 60)
print("  Leg 1: 'Decrease 50+ bps' YES — 348.49 shares @ $0.007 = $2.44")
print("  Leg 2: 'Increase 25+ bps' YES — 348.49 shares @ $0.006 = $2.09")
print("  Total cost: $4.53")
print()
print("  MISSING outcomes we DIDN'T buy:")
print("    - No Change")
print("    - Decrease 25 bps") 
print("    - Decrease 25-50 bps")
print("    - etc.")
print()
print("  This means: if Fed keeps rates SAME → BOTH our bets lose = -$4.53")
print("  Only profit IF Fed does something extreme (decrease 50+ OR increase 25+)")
print()
print("  >> THIS IS NOT A HEDGE — it's two speculative long-shot bets! <<")

# 3. Our other positions too
print("\n" + "=" * 60)
print("OTHER POSITIONS")
print("=" * 60)
print("  Bitcoin below $80K (NO) — 2.19 shares @ $0.89 = $1.95")
print("    → We bet Bitcoin STAYS above $80K")
print("    → This is a single bet, NOT a hedge")
print()
print("  Fed No Change (YES) — 2.15 shares @ $0.93 = $2.00")  
print("    → We bet Fed keeps rates same")
print("    → This CONTRADICTS our other Fed bets!")
print("    → Also a single bet, NOT a hedge")

# 4. Summary
print("\n" + "=" * 60)
print("REAL SITUATION")
print("=" * 60)
print(f"  Starting balance: $28.27")
print(f"  Spent on trades: $8.48")
print(f"  Remaining USDC.e on Polymarket: $19.79")
print(f"  Total account value: $19.79 + positions")
print()
print("  Our positions are SPECULATIVE BETS, not hedges.")
print("  They could win big (unlikely) or lose everything (likely).")
