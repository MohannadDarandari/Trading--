"""Research Polymarket BTC 5-minute up/down market structure."""
import httpx
import json

# The event slug from the URL
EVENT_SLUG = "btc-updown-5m-1771257900"

print("="*60)
print("  🔍 RESEARCHING BTC 5-MIN MARKETS")
print("="*60)

# Try to find via Gamma API
print("\n  1. Searching Gamma API for BTC 5-min events...")
r = httpx.get("https://gamma-api.polymarket.com/events", params={
    "slug": EVENT_SLUG,
    "closed": "false",
}, timeout=15)
print(f"    Status: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    print(f"    Found: {len(data)} events")
    for event in data:
        print(f"\n    Event: {event.get('title', '?')}")
        print(f"    ID: {event.get('id')}")
        print(f"    Slug: {event.get('slug')}")
        print(f"    End: {event.get('endDate')}")
        markets = event.get('markets', [])
        print(f"    Markets: {len(markets)}")
        for m in markets[:5]:
            print(f"      - {m.get('question')} | Price: {m.get('outcomePrices')} | ID: {m.get('id')}")

# Search for active BTC 5-min events
print("\n  2. Searching for ALL active BTC 5-min events...")
r = httpx.get("https://gamma-api.polymarket.com/events", params={
    "limit": 20,
    "active": "true",
    "closed": "false",
    "tag": "crypto",
}, timeout=15)
if r.status_code == 200:
    data = r.json()
    btc_5m = [e for e in data if '5' in e.get('title', '') and ('btc' in e.get('title', '').lower() or 'bitcoin' in e.get('title', '').lower())]
    print(f"    Found {len(btc_5m)} BTC 5-min events out of {len(data)} crypto events")
    for event in btc_5m[:5]:
        print(f"\n    Event: {event.get('title')}")
        print(f"    Slug: {event.get('slug')}")
        markets = event.get('markets', [])
        for m in markets[:3]:
            print(f"      - {m.get('question')} | Prices: {m.get('outcomePrices')}")

# Search broader
print("\n  3. Searching for 'btc-updown' events...")
r = httpx.get("https://gamma-api.polymarket.com/events", params={
    "limit": 30,
    "active": "true",
    "closed": "false",
}, timeout=15)
if r.status_code == 200:
    data = r.json()
    updown = [e for e in data if 'updown' in e.get('slug', '').lower() or '5m' in e.get('slug', '').lower() or 'up or down' in e.get('title', '').lower()]
    print(f"    Found {len(updown)} up/down events")
    for event in updown[:10]:
        print(f"\n    Event: {event.get('title')}")
        print(f"    Slug: {event.get('slug')}")
        print(f"    End: {event.get('endDate')}")
        markets = event.get('markets', [])
        for m in markets[:3]:
            q = m.get('question', '')
            prices = m.get('outcomePrices', '')
            cid = m.get('clobTokenIds', '')
            print(f"      - Q: {q}")
            print(f"        Prices: {prices} | CLOB: {str(cid)[:80]}")

# Try direct slug search with different patterns  
print("\n  4. Trying different search patterns...")
for pattern in ["btc-updown", "bitcoin up or down", "btc 5 minute", "bitcoin 5-minute"]:
    r = httpx.get("https://gamma-api.polymarket.com/events", params={
        "limit": 5,
        "title": pattern,
    }, timeout=10)
    if r.status_code == 200:
        data = r.json()
        if data:
            print(f"\n    Pattern '{pattern}': {len(data)} results")
            for e in data[:3]:
                print(f"      {e.get('title')} | slug={e.get('slug')}")
