import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from agent.advanced_analyzer import AdvancedMarketAnalyzer

analyzer = AdvancedMarketAnalyzer()
print(f"Fetch mode: {analyzer.last_fetch_mode}")

markets = analyzer.get_active_markets(limit=20, min_volume=500)
print(f"\nFetch mode after: {analyzer.last_fetch_mode}")
print(f"Markets returned: {len(markets)}")

if markets:
    print("\nTop 5 markets:")
    for i, m in enumerate(markets[:5], 1):
        q = m.get('question', m.get('title', '?'))[:70]
        v = float(m.get('volume', 0))
        outcomes = m.get('outcomes', [])
        prices = [float(o.get('price', 0)) for o in outcomes[:2]]
        print(f"  {i}. {q}")
        print(f"     Volume: ${v:,.0f}  |  Prices: {prices}")
    
    print("\n\n--- Analyzing for opportunities ---")
    opps = analyzer.find_best_opportunities(markets, min_confidence=0.3)
    print(f"\nOpportunities found: {len(opps)}")
    
    for i, opp in enumerate(opps[:3], 1):
        print(f"\n  #{i}: {opp['question'][:60]}")
        print(f"      Type: {opp['opportunity_type']} | Confidence: {opp['confidence']*100:.0f}%")
        print(f"      YES: {opp['current_price_yes']:.2f} | NO: {opp['current_price_no']:.2f}")
        print(f"      Expected Return: {opp['expected_return']*100:.1f}%")
else:
    print("NO MARKETS - still blocked or API issue")
