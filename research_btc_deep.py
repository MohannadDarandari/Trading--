"""Deep research on BTC 5-min market - find pattern for upcoming markets."""
import httpx
import json
from datetime import datetime, timezone, timedelta

print("="*60)
print("  🔍 DEEP RESEARCH: BTC 5-MIN MARKETS")
print("="*60)

# The known event
KNOWN_SLUG = "btc-updown-5m-1771257900"

# Get full event details
r = httpx.get(f"https://gamma-api.polymarket.com/events", params={"slug": KNOWN_SLUG}, timeout=15)
event = r.json()[0]
print(f"\n  Known event: {event['title']}")
print(f"  Slug pattern: {event['slug']}")
print(f"  Start: {event.get('startDate')}")
print(f"  End: {event.get('endDate')}")

# The slug pattern is: btc-updown-5m-{UNIX_TIMESTAMP}
# 1771257900 is a unix timestamp
ts = 1771257900
dt = datetime.fromtimestamp(ts, tz=timezone.utc)
print(f"\n  Decoded timestamp: {ts} = {dt.isoformat()}")
print(f"  That's: {dt.strftime('%B %d %Y %H:%M:%S UTC')}")

# So the pattern is: every 5 minutes there's a new event
# Let's find upcoming ones
now = datetime.now(tz=timezone.utc)
print(f"\n  Current time: {now.isoformat()}")

# Calculate next 5-minute windows
# Round up to next 5-minute mark
minute = now.minute
next_5 = (minute // 5 + 1) * 5
if next_5 >= 60:
    next_start = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
else:
    next_start = now.replace(minute=next_5, second=0, microsecond=0)

print(f"\n  Upcoming 5-min windows:")
for i in range(6):
    window_start = next_start + timedelta(minutes=5*i)
    window_end = window_start + timedelta(minutes=5)
    ts_start = int(window_start.timestamp())
    slug = f"btc-updown-5m-{ts_start}"
    print(f"    {window_start.strftime('%H:%M')}-{window_end.strftime('%H:%M')} UTC | slug: {slug}")

# Try to find the NEXT upcoming market
print("\n  Searching for upcoming markets...")
for i in range(12):
    window_start = next_start + timedelta(minutes=5*i)
    ts_start = int(window_start.timestamp())
    slug = f"btc-updown-5m-{ts_start}"
    
    r = httpx.get("https://gamma-api.polymarket.com/events", params={"slug": slug}, timeout=10)
    if r.status_code == 200 and r.json():
        ev = r.json()[0]
        mkts = ev.get('markets', [])
        print(f"  ✅ FOUND: {slug}")
        print(f"     Title: {ev['title']}")
        print(f"     End: {ev.get('endDate')}")
        if mkts:
            m = mkts[0]
            print(f"     Market ID: {m['id']}")
            print(f"     Prices: {m.get('outcomePrices')}")
            print(f"     Outcomes: {m.get('outcomes')}")
            print(f"     CLOB Tokens: {m.get('clobTokenIds')}")
            print(f"     Condition ID: {m.get('conditionId')}")
    else:
        print(f"  ❌ {slug} - not found yet")

# Also search by looking for multiple active BTC markets
print("\n  Searching all active crypto events for 'up' or 'down'...")
r = httpx.get("https://gamma-api.polymarket.com/events", params={
    "limit": 100,
    "active": "true",
    "closed": "false",
}, timeout=15)
if r.status_code == 200:
    all_events = r.json()
    btc_events = [e for e in all_events if 'bitcoin' in e.get('title', '').lower() or 'btc' in e.get('slug', '').lower()]
    print(f"  Found {len(btc_events)} BTC-related events out of {len(all_events)}")
    for e in btc_events[:15]:
        print(f"    - {e['title'][:80]} | slug: {e['slug'][:50]}")

# Check CLOB for the market
print("\n  Checking CLOB for market details...")
if event.get('markets'):
    m = event['markets'][0]
    clob_ids = m.get('clobTokenIds')
    condition_id = m.get('conditionId')
    print(f"  Market: {m['question']}")
    print(f"  Condition: {condition_id}")
    print(f"  CLOB Token IDs: {clob_ids}")
    print(f"  Outcomes: {m.get('outcomes')}")
    
    # Get order book
    if clob_ids:
        token_ids = json.loads(clob_ids) if isinstance(clob_ids, str) else clob_ids
        for tid in token_ids:
            r2 = httpx.get(f"https://clob.polymarket.com/book", params={"token_id": tid}, timeout=10)
            if r2.status_code == 200:
                book = r2.json()
                bids = book.get('bids', [])[:3]
                asks = book.get('asks', [])[:3]
                print(f"\n  Order book for token {tid[:20]}...:")
                print(f"    Bids: {bids}")
                print(f"    Asks: {asks}")
