"""Quick integration test — runs 1 scan, sends test report to Telegram."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from simulator.engine import SimulationEngine

engine = SimulationEngine()

print("=== Running 1 scan cycle ===")
engine._scan()

print(f"\nOpportunities found: {len(engine.w_opps)}")
for o in engine.w_opps[:10]:
    print(f"  {o.market_slug[:25]} | type={o.edge_type} | edge={o.edge_signal:.2f}% | "
          f"askY={o.best_ask_yes} askN={o.best_ask_no} | cost={o.unit_cost_signal}")

print(f"\nPending checks: {len(engine.pending)}")
print("\n=== Sending test report to Telegram ===")
engine._report(final=True)
print("DONE. Check Telegram!")
