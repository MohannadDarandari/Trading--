"""Check local bot database for executed trades."""
import sqlite3, os, json
os.chdir(r"C:\Users\mdara\OneDrive\Desktop\DarkOps HQ\Trading$$")

# Find the database
for f in ["data/polyclaw.db", "polyclaw.db", "data/hedge_bot.db", "hedge_bot.db"]:
    if os.path.exists(f):
        print(f"Found DB: {f}")
        db = sqlite3.connect(f)
        db.row_factory = sqlite3.Row
        
        # Check tables
        tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        print(f"Tables: {tables}")
        
        for t in tables:
            count = db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            print(f"  {t}: {count} rows")
        
        # Check orders
        if 'orders' in tables:
            print("\n=== ORDERS ===")
            cols = [r[1] for r in db.execute("PRAGMA table_info(orders)").fetchall()]
            print(f"Columns: {cols}")
            for row in db.execute("SELECT * FROM orders ORDER BY rowid DESC LIMIT 10"):
                d = dict(row)
                print(json.dumps(d, indent=2, default=str))
        
        # Check fills
        if 'fills' in tables:
            print("\n=== FILLS ===")
            for row in db.execute("SELECT * FROM fills ORDER BY rowid DESC LIMIT 10"):
                d = dict(row)
                print(json.dumps(d, indent=2, default=str))
        
        # Check incidents
        if 'incidents' in tables:
            print("\n=== INCIDENTS ===")
            for row in db.execute("SELECT * FROM incidents ORDER BY rowid DESC LIMIT 5"):
                d = dict(row)
                print(json.dumps(d, indent=2, default=str))
        
        db.close()
        break
else:
    print("No database found! Checking data/...")
    if os.path.exists("data"):
        print(os.listdir("data"))
    else:
        print("No data/ directory")
