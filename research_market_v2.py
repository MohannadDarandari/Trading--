#!/usr/bin/env python3
"""Research the ACTUAL Polymarket BTC 5-min market structure."""
import httpx, json, time
from datetime import datetime, timezone, timedelta

now = datetime.now(tz=timezone.utc)
minute = now.minute
c = httpx.Client(timeout=10)

# Try current and next 5-min windows
for offset in [-1, 0, 1, 2]:
    target_min = ((minute // 5) + offset) * 5
    if target_min < 0:
        t = now.replace(minute=0, second=0, microsecond=0) - timedelta(minutes=abs(target_min))
    elif target_min >= 60:
        t = now.replace(minute=0, second=0, microsecond=0) + timedelta(minutes=target_min)
    else:
        t = now.replace(minute=target_min, second=0, microsecond=0)
    
    ts = int(t.timestamp())
    slug = f"btc-updown-5m-{ts}"
    print(f"\n{'='*60}")
    print(f"Trying: {slug}")
    print(f"Window: {t.strftime('%H:%M:%S')} UTC")
    
    r = c.get("https://gamma-api.polymarket.com/events", params={"slug": slug})
    data = r.json()
    
    if not data:
        print("  NO EVENT FOUND")
        continue
    
    ev = data[0]
    print(f"  Title: {ev.get('title')}")
    desc = ev.get("description", "")
    print(f"  Description: {desc[:500]}")
    
    markets = ev.get("markets", [])
    print(f"  Markets: {len(markets)}")
    
    for m in markets[:5]:
        q = m.get("question", "")
        outcomes = m.get("outcomes")
        prices = m.get("outcomePrices")
        clob = m.get("clobTokenIds")
        mdesc = m.get("description", "")
        
        print(f"\n  --- Market ---")
        print(f"  Question: {q}")
        print(f"  Outcomes: {outcomes}")
        print(f"  Prices: {prices}")
        print(f"  CLOB IDs: {clob}")
        print(f"  Market Desc: {str(mdesc)[:300]}")
        
        # Check ALL fields for "price to beat" or reference price
        for key in ["question", "description", "title", "groupItemTitle"]:
            val = m.get(key, "")
            if val and ("price" in str(val).lower() or "beat" in str(val).lower() or "$" in str(val)):
                print(f"  ** Found price ref in '{key}': {str(val)[:200]}")

# Also try direct search
print("\n\n===== SEARCH BY TITLE =====")
r = c.get("https://gamma-api.polymarket.com/events", params={
    "limit": 20,
    "active": "true",
    "closed": "false",
    "title": "Bitcoin Up or Down"
})
for ev in r.json()[:5]:
    print(f"\n  Title: {ev.get('title')}")
    print(f"  Slug: {ev.get('slug')}")
    desc = ev.get("description", "")
    print(f"  Desc: {desc[:300]}")
    for m in ev.get("markets", [])[:2]:
        print(f"    Q: {m.get('question')}")
        print(f"    Outcomes: {m.get('outcomes')}")
        print(f"    Prices: {m.get('outcomePrices')}")
        print(f"    Desc: {str(m.get('description',''))[:200]}")

print("\n\n===== SEARCH BY TAG CRYPTO =====")
r = c.get("https://gamma-api.polymarket.com/events", params={
    "limit": 30,
    "active": "true",
    "closed": "false",
    "tag": "crypto",
    "order": "startDate",
    "ascending": "false"
})
for ev in r.json()[:10]:
    slug = ev.get("slug", "")
    if "updown" in slug or "5m" in slug or "up-or-down" in slug:
        print(f"\n  Title: {ev.get('title')}")
        print(f"  Slug: {slug}")
        desc = ev.get("description", "")
        print(f"  Desc: {desc[:300]}")
