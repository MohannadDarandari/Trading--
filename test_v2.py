#!/usr/bin/env python3
"""Quick test of BTC predictor v3."""
from btc_predictor import PredictionEngine

engine = PredictionEngine()
pred = engine.predict()

if pred:
    print(f"Direction:  {pred.direction}")
    print(f"Confidence: {pred.confidence}%")
    print(f"Tier:       {pred.tier}")
    print(f"BTC Price:  ${pred.price:,.2f}")
    print()
    print("Reasons:")
    for r in pred.reasons:
        print(f"  {r}")
    print()
    print("Scores:")
    for k, v in pred.scores.items():
        bar = "+" * max(0, int(v)) + "-" * max(0, int(-v))
        print(f"  {k:12s}: {v:+5.1f}  {bar}")
else:
    print("No prediction")
