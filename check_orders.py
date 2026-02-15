"""Check successful orders and diagnose minimum size issue."""
import sqlite3, os, json
os.chdir(r"C:\Users\mdara\OneDrive\Desktop\DarkOps HQ\Trading$$")

db = sqlite3.connect("data/hedge_bot.db")
db.row_factory = sqlite3.Row

# Successful orders
print("=== SUCCESSFUL ORDERS ===")
for row in db.execute("SELECT * FROM orders WHERE status='submitted'"):
    d = dict(row)
    print(json.dumps(d, indent=2, default=str))

# All unique opportunity names
print("\n=== ALL OPPORTUNITIES ===")
for row in db.execute("SELECT opportunity_name, status, COUNT(*) as cnt, GROUP_CONCAT(error) as errors FROM orders GROUP BY opportunity_name, status"):
    d = dict(row)
    name = d['opportunity_name']
    print(f"  {name} | {d['status']} x{d['cnt']} | {(d.get('errors','') or '')[:100]}")

# First few orders (Fed Rates, Bitcoin)
print("\n=== FIRST 5 ORDERS ===")
for row in db.execute("SELECT * FROM orders ORDER BY id ASC LIMIT 5"):
    d = dict(row)
    print(json.dumps(d, indent=2, default=str))

db.close()
