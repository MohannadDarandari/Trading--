"""
Show EXACTLY where the $28 went and when each position resolves.
Uses market IDs from our actual orders.
"""
import asyncio, sys, os, json
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

import httpx

async def main():
    # Our EXACT market IDs from the database
    market_ids = {
        "654412": {"name": "Fed Decrease 50+ bps", "shares": 348.49, "price": 0.0065, "side": "YES"},
        "654415": {"name": "Fed Increase 25+ bps", "shares": 348.49, "price": 0.0055, "side": "YES"},
        "654414": {"name": "Fed No Change", "shares": 2.15, "price": 0.925, "side": "YES"},
        "1345680": {"name": "Bitcoin < $80K", "shares": 2.19, "price": 0.885, "side": "NO"},
    }
    
    print("="*70)
    print("  💰 وين راحت الـ $28 دولار — تفصيل كامل")
    print("="*70)
    
    total_spent = 0
    total_current = 0
    total_payout_win = 0
    
    for mid, pos in market_ids.items():
        # Fetch market details from Gamma API
        try:
            async with httpx.AsyncClient(timeout=15) as http:
                resp = await http.get(f"https://gamma-api.polymarket.com/markets/{mid}")
                if resp.status_code == 200:
                    data = resp.json()
                else:
                    # Try CLOB
                    resp2 = await http.get(f"https://clob.polymarket.com/markets/{mid}")
                    data = resp2.json() if resp2.status_code == 200 else {}
        except Exception as e:
            data = {}
        
        question = data.get("question", pos["name"])
        end_date = data.get("endDate") or data.get("end_date_iso") or data.get("endDateIso") or "???"
        resolved = data.get("resolved", False)
        closed = data.get("closed", False)
        
        # Current prices
        outcome_prices = data.get("outcomePrices")
        if isinstance(outcome_prices, str):
            try:
                prices = json.loads(outcome_prices)
                yes_price = float(prices[0]) if prices else 0
                no_price = float(prices[1]) if len(prices) > 1 else 1.0 - yes_price
            except:
                yes_price = 0
                no_price = 0
        elif isinstance(outcome_prices, list):
            yes_price = float(outcome_prices[0]) if outcome_prices else 0
            no_price = float(outcome_prices[1]) if len(outcome_prices) > 1 else 1.0 - yes_price
        else:
            yes_price = float(data.get("yes_price", 0) or 0)
            no_price = float(data.get("no_price", 0) or 0)
        
        current_price = yes_price if pos["side"] == "YES" else no_price
        
        cost = pos["shares"] * pos["price"]
        total_spent += cost
        
        current_value = pos["shares"] * current_price
        total_current += current_value
        
        # If this wins (resolves YES for YES position, NO for NO position)
        payout_if_win = pos["shares"] * 1.0  # each share pays $1 if correct
        
        status = "✅ RESOLVED" if resolved else ("🔒 CLOSED" if closed else "⏳ ACTIVE")
        
        print(f"\n{'─'*70}")
        print(f"  📌 {question[:65]}")
        print(f"  Position: {pos['side']} | Shares: {pos['shares']:.2f}")
        print(f"  ────────────────────────────────")
        print(f"  💸 دفعت:           ${cost:.2f}")
        print(f"  📊 سعر الشراء:     ${pos['price']:.4f}")
        print(f"  📈 سعر الحين:      ${current_price:.4f}")
        print(f"  💵 قيمتها الحين:    ${current_value:.2f}")
        if current_value > cost:
            print(f"  🟢 ربح حالي:       +${current_value - cost:.2f}")
        else:
            print(f"  🔴 خسارة حالية:    -${cost - current_value:.2f}")
        print(f"  🏆 لو فازت:        ${payout_if_win:.2f}")
        print(f"  📅 تاريخ الانتهاء: {end_date[:10] if end_date != '???' else '???'}")
        print(f"  حالة السوق:        {status}")
        total_payout_win += payout_if_win
    
    # Also check wallet + Polymarket balance
    print(f"\n{'='*70}")
    print(f"  📊 ملخص كامل")
    print(f"{'='*70}")
    print(f"  💰 رأس المال الأصلي:    $28.00")
    print(f"  💸 إجمالي المدفوع:       ${total_spent:.2f}")
    print(f"  💵 قيمة الصفقات الحين:   ${total_current:.2f}")
    print(f"  🏦 باقي في Polymarket:   ${28 - total_spent:.2f} (collateral)")
    print(f"  📦 المجموع:              ${total_current + (28 - total_spent):.2f}")
    print(f"{'='*70}")
    
    # Check on-chain USDC.e balance too
    try:
        rpc = os.getenv("CHAINSTACK_NODE")
        if rpc:
            async with httpx.AsyncClient(timeout=10) as http:
                # Check USDC.e balance
                payload = {
                    "jsonrpc": "2.0", "id": 1, "method": "eth_call",
                    "params": [{
                        "to": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
                        "data": "0x70a08231000000000000000000000000Add5cf1e1d6992C0130C3a89094F300fA71d32E5"
                    }, "latest"]
                }
                resp = await http.post(rpc, json=payload)
                result = resp.json().get("result", "0x0")
                usdc_balance = int(result, 16) / 1e6
                print(f"  💳 USDC.e في المحفظة:    ${usdc_balance:.2f}")
    except:
        pass

asyncio.run(main())
