"""
Generate direct links to monitor all positions on Polymarket.
"""
import asyncio, httpx

WALLET = "0xAdd5cf1e1d6992C0130C3a89094F300fA71d32E5"

positions = {
    "654412": "Fed Decrease 50+ bps",
    "654415": "Fed Increase 25+ bps", 
    "654414": "Fed No Change",
    "1345680": "Bitcoin $80K",
}

async def main():
    print("="*60)
    print("  🔗 روابط مراقبة حسابك على Polymarket")
    print("="*60)
    
    print(f"\n  📱 محفظتك: {WALLET}")
    
    print(f"\n  🔍 PolygonScan (كل المعاملات):")
    print(f"  https://polygonscan.com/address/{WALLET}")
    
    print(f"\n  🏠 Polymarket Profile:")
    print(f"  https://polymarket.com/profile/{WALLET}")
    
    print(f"\n  📊 صفقاتك:")
    
    for mid, name in positions.items():
        try:
            async with httpx.AsyncClient(timeout=10) as http:
                resp = await http.get(f"https://gamma-api.polymarket.com/markets/{mid}")
                if resp.status_code == 200:
                    data = resp.json()
                    slug = data.get("slug") or data.get("market_slug") or data.get("conditionId", "")
                    question = data.get("question", name)
                    group_slug = data.get("groupSlug", "")
                    
                    if group_slug:
                        url = f"https://polymarket.com/event/{group_slug}"
                    elif slug:
                        url = f"https://polymarket.com/market/{slug}"
                    else:
                        url = f"https://polymarket.com/markets/{mid}"
                    
                    print(f"\n  📌 {question[:60]}")
                    print(f"     {url}")
                else:
                    print(f"\n  📌 {name}: https://polymarket.com/markets/{mid}")
        except Exception as e:
            print(f"\n  📌 {name}: error - {e}")

    print(f"\n{'='*60}")
    print(f"  💡 نصيحة: افتح Polymarket.com واربط MetaMask")
    print(f"     عشان تشوف الصفقات + الرصيد + تقدر تبيع")
    print(f"{'='*60}")

asyncio.run(main())
