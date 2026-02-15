import sqlite3

for db in ['data/hedge_bot.db', 'data/hedge_bot_old.db']:
    try:
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM orders WHERE status='submitted' ORDER BY ts").fetchall()
        print(f"\n=== {db} ({len(rows)} submitted) ===")
        for r in rows:
            name = r["opportunity_name"]
            mid = r["market_id"]
            tid = r["token_id"][:50]
            side = r["side"]
            size = r["size"]
            price = r["price"]
            oid = (r["order_id"] or "N/A")[:50]
            print(f"  {name}")
            print(f"    market_id: {mid}")
            print(f"    token_id:  {tid}")
            print(f"    {side} {size} @ ${price} = ${size*price:.2f}")
            print(f"    order_id:  {oid}")
            print()
        conn.close()
    except Exception as e:
        print(f"{db}: {e}")
