"""Quick test of the predictor - single analysis run."""
import sys
sys.path.insert(0, ".")

from btc_predictor import PredictionEngine, TelegramAlerter, MIN_CONFIDENCE

engine = PredictionEngine()
alerter = TelegramAlerter()

print("  🔍 Running full BTC analysis...")
signal = engine.analyze()

if signal:
    print(f"\n  ✅ PREDICTION: {signal.direction}")
    print(f"  📊 Confidence: {signal.confidence}%")
    print(f"  💰 BTC Price: ${signal.btc_price:,.2f}")
    print(f"  ⏰ Window: {signal.window_start.strftime('%H:%M')}-{signal.window_end.strftime('%H:%M')} UTC")
    print(f"  🔗 {signal.polymarket_url}")
    
    # Print all indicators
    print(f"\n  📊 INDICATORS:")
    up_votes = []
    down_votes = []
    neutral = []
    for name, (direction, weight) in sorted(signal.indicators.items(), key=lambda x: x[1][1], reverse=True):
        icon = "⬆" if direction == "UP" else "⬇" if direction == "DOWN" else "↔"
        print(f"    {icon} {name}: {direction} (weight: {weight:.1f})")
        if direction == "UP": up_votes.append((name, weight))
        elif direction == "DOWN": down_votes.append((name, weight))
        else: neutral.append(name)
    
    print(f"\n  Summary: {len(up_votes)}⬆ vs {len(down_votes)}⬇ ({len(neutral)} neutral)")
    print(f"  UP weight: {sum(w for _, w in up_votes):.1f} | DOWN weight: {sum(w for _, w in down_votes):.1f}")
    
    if signal.confidence >= MIN_CONFIDENCE:
        print(f"\n  📢 Sending to Telegram...")
        alerter.send_signal(signal)
        print(f"  ✅ Sent!")
    else:
        print(f"\n  ⚠ Too low confidence to send ({signal.confidence}% < {MIN_CONFIDENCE}%)")
else:
    print("  ❌ Analysis failed!")
