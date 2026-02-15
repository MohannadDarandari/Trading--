"""
Check the on-chain database for our actual trade details to find exact market IDs.
"""
import sqlite3, os

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "hedge_bot.db")
OLD_DB = os.path.join(os.path.dirname(__file__), "data", "hedge_bot_old.db")

for label, path in [("CURRENT DB", DB_PATH), ("OLD DB", OLD_DB)]:
    if not os.path.exists(path):
        print(f"\n{label}: not found at {path}")
        continue
    
    print(f"\n{'='*65}")
    print(f"  {label}: {path}")
    print(f"{'='*65}")
    
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    
    # Get successful orders
    rows = conn.execute("""
        SELECT opp_name, market_id, token_id, side, price, size, 
               order_id, status, error, timestamp
        FROM orders 
        WHERE status = 'submitted' OR order_id IS NOT NULL
        ORDER BY timestamp
    """).fetchall()
    
    print(f"\n  ✅ SUCCESSFUL ORDERS ({len(rows)}):")
    for r in rows:
        print(f"    {r['timestamp'][:19]} | {r['opp_name'][:40]}")
        print(f"      Market: {r['market_id']}")
        print(f"      Token:  {r['token_id'][:30]}...")
        print(f"      {r['side']} {r['size']} @ ${r['price']} = ${r['size'] * r['price']:.2f}")
        print(f"      Order:  {r['order_id'][:30] if r['order_id'] else 'N/A'}...")
        print()
    
    conn.close()
