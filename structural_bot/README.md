# Structural 15m Polymarket Bot (BTC/ETH)

This project implements a production-grade structural arbitrage bot for 15-minute BTC/ETH Up/Down markets on Polymarket. It trades only when depth-aware VWAP confirms YES+NO total cost < threshold after buffers. No prediction or directional bets.

## Quick Start

```bash
cd structural_bot
py -m pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` with your Telegram and Polymarket credentials.

### Run scanner + executor

```bash
py -m app.main
```

### Run dashboard

```bash
streamlit run app/dashboard.py
```

## Live Safety

- Live trading is **disabled by default**.
- Set `LIVE_ENABLED=true` in `.env` **only after** 24-72h simulation passes.

## CLOB Auth Notes

`app/polymarket_clob.py` includes a signing stub. Replace it with the official Polymarket signing method from their docs. The bot will run in read-only mode without auth, but live trading requires valid auth headers.

## How It Works

- **Discovery (Gamma API)**: At startup, find the BTC/ETH 15m Up/Down markets and cache IDs in SQLite.
- **Scan (CLOB API)**: Every second, fetch YES/NO orderbooks (top 10), compute VWAP for a tiny quantity.
- **Edge check**: `unit_cost <= 1 - (fee_buffer + slippage_buffer + safety_margin)`.
- **Execution**: Place two limit buy orders near-simultaneously. If only one fills, flatten immediately.

## VWAP Math (Why It Matters)

For each side (YES/NO), we compute a depth-aware VWAP to buy quantity `Q`:

$$
VWAP = \frac{\sum_i p_i \cdot q_i}{\sum_i q_i}
$$

If YES + NO VWAP cost per unit is under threshold, the trade has structural edge.

## Files

```
app/
  main.py            # scanner + executor + scheduler
  polymarket_clob.py # CLOB client (read/write)
  gamma.py           # discovery at startup only
  vwap.py            # vwap and depth utilities
  risk.py            # kill switch + limits
  exec.py            # order placement/cancel/flatten logic
  db.py              # sqlite layer
  telegram.py        # alerts + reports + csv attachments
  dashboard.py       # streamlit UI
config.yml
requirements.txt
.env.example
```

## Notes

- This repo includes a correlation module in simulation mode only.
- Do not enable live trading until metrics pass and your wallet is funded.
