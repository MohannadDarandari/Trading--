"""Check ALL records for this run."""
import sqlite3, os, json
os.chdir(r"C:\Users\mdara\OneDrive\Desktop\DarkOps HQ\Trading$$")

db = sqlite3.connect("data/hedge_bot.db")
db.row_factory = sqlite3.Row

# Check all tables
for t in ['orders', 'incidents', 'depth_checks', 'opportunities']:
    rows = db.execute(f"SELECT * FROM {t}").fetchall()
    print(f"\n=== {t.upper()} ({len(rows)} rows) ===")
    for r in rows:
        d = dict(r)
        # Compact print
        if t == 'orders':
            print(f"  #{d['id']} | {d['opportunity_name'][:40]} | {d['status']} | size={d.get('size',0):.2f} @ ${d.get('price',0):.4f} | {(d.get('error','') or '')[:60]}")
        elif t == 'incidents':
            print(f"  #{d['id']} | {d['incident_type']} | {d.get('details','')} | {d.get('kill_reason','')}")
        elif t == 'opportunities':
            print(f"  #{d['id']} | {d.get('name','')[:40]} | exec={d.get('executed','')} | profit=${d.get('profit_per_dollar',0):.4f}")
        elif t == 'depth_checks':
            print(f"  #{d['id']} | pass={d.get('passed','')} | depth=${d.get('depth_usd',0):.2f} | spread={d.get('spread',0):.4f}")

db.close()
