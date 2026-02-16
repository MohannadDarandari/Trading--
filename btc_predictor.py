#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║  🎯 BTC 5-MIN PREDICTOR v2 — SMART PROBABILITY MODEL          ║
║  Based on: Distance from PRICE TO BEAT + Volatility + Momentum ║
║  + Polymarket Market Bias + Order Flow                          ║
╚══════════════════════════════════════════════════════════════════╝

HOW THIS MARKET WORKS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Every 5 minutes a new market opens on Polymarket
• "PRICE TO BEAT" = BTC price at the EXACT START of the 5-min window
• "Up" wins if BTC price at END >= PRICE TO BEAT
• "Down" wins if BTC price at END < PRICE TO BEAT
• Resolution source: Chainlink BTC/USD

STRATEGY:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. BEFORE window starts: Pre-analyze momentum & direction
2. WHEN window starts (first 30-60s): 
   - Record PRICE TO BEAT (BTC price at window start)
   - Check how far BTC has moved from PRICE TO BEAT
   - Calculate probability using:
     a) Distance from PRICE TO BEAT (statistical model)
     b) 5-min volatility (how much can BTC move in remaining time)
     c) Momentum (which way is BTC moving right now)
     d) Polymarket prices (what does the crowd think)
     e) Order flow (who's buying vs selling)
3. SIGNAL if combined confidence > 70%
4. Best edge: when price is far from PRICE TO BEAT AND momentum confirms

SIGNAL TIMING:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Send signal 30-90 seconds INTO the window
• At this point: PRICE TO BEAT is known, prices still near 50/50
• Earlier = more profit potential, less certainty
• We optimize for: moderate certainty (70%+) at good entry prices

TIER SYSTEM:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔴 SKIP    (0-69%)  — No signal
🟡 WATCH   (70-79%) — Low confidence alert
🟢 SIGNAL  (80-89%) — Strong signal
🔥 SNIPER  (90%+)   — Maximum confidence
"""

import os
import sys
import json
import time
import math
import traceback
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict

import httpx

# ===========================================================================
# CONFIGURATION
# ===========================================================================

TELEGRAM_TOKEN = "8331165268:AAEA84wTDNeFuPhRJkjLiUqxxkaPEuL2B-o"
TELEGRAM_CHAT_IDS = ["1688623770", "1675476723"]

BINANCE_API = "https://api.binance.com/api/v3"
GAMMA_API = "https://gamma-api.polymarket.com"

SCAN_INTERVAL = 10        # Check every 10 seconds (we need fast reaction)
MIN_CONFIDENCE = 70       # Minimum to send any signal

# When to signal: seconds AFTER window starts
SIGNAL_WINDOW_START = 30  # Start analyzing 30s into window
SIGNAL_WINDOW_END = 180   # Stop analyzing 180s into window (3 min)

# ===========================================================================
# NORMAL CDF (for probability calculation)
# ===========================================================================

def norm_cdf(x):
    """Standard normal CDF using error function approximation."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

# ===========================================================================
# DATA STRUCTURES
# ===========================================================================

@dataclass
class Candle:
    timestamp: float
    open: float
    high: float
    low: float
    close: float
    volume: float

@dataclass
class MarketData:
    slug: str
    title: str
    up_price: float      # Current Up price (0-1)
    down_price: float     # Current Down price (0-1)
    up_token_id: str
    down_token_id: str
    window_start: datetime
    window_end: datetime
    url: str

@dataclass 
class Signal:
    direction: str        # UP / DOWN
    confidence: float     # 0-100
    tier: str             # SKIP / WATCH / SIGNAL / SNIPER
    reasons: List[str]    # Human-readable reasons
    btc_price: float      # Current BTC price
    price_to_beat: float  # Window start price
    distance_usd: float   # Current - PRICE_TO_BEAT
    market_bias: float    # Polymarket Up price (0-1)
    window_start: datetime
    window_end: datetime
    time_left: int        # Seconds left in window
    slug: str
    url: str

# ===========================================================================
# PRICE ENGINE
# ===========================================================================

class PriceEngine:
    def __init__(self):
        self.client = httpx.Client(timeout=10)
        self._klines_cache = {}
        self._klines_time = {}
    
    def get_btc_price(self) -> float:
        """Get current BTC/USDT price."""
        try:
            r = self.client.get(f"{BINANCE_API}/ticker/price", 
                                params={"symbol": "BTCUSDT"})
            if r.status_code == 200:
                return float(r.json()["price"])
        except:
            pass
        return 0.0
    
    def get_klines(self, interval: str = "1m", limit: int = 100) -> List[Candle]:
        """Get BTC/USDT klines."""
        cache_key = f"{interval}_{limit}"
        now = time.time()
        if cache_key in self._klines_cache and now - self._klines_time.get(cache_key, 0) < 3:
            return self._klines_cache[cache_key]
        
        try:
            r = self.client.get(f"{BINANCE_API}/klines", params={
                "symbol": "BTCUSDT", "interval": interval, "limit": limit
            })
            if r.status_code == 200:
                candles = [Candle(
                    timestamp=k[0]/1000, open=float(k[1]), high=float(k[2]),
                    low=float(k[3]), close=float(k[4]), volume=float(k[5])
                ) for k in r.json()]
                self._klines_cache[cache_key] = candles
                self._klines_time[cache_key] = now
                return candles
        except Exception as e:
            print(f"  ⚠ klines error: {e}")
        return self._klines_cache.get(cache_key, [])
    
    def get_btc_price_at_time(self, target_ts: int) -> Optional[float]:
        """Get BTC price at a specific timestamp (for PRICE TO BEAT)."""
        try:
            r = self.client.get(f"{BINANCE_API}/klines", params={
                "symbol": "BTCUSDT",
                "interval": "1m", 
                "startTime": target_ts * 1000,
                "limit": 1
            })
            if r.status_code == 200:
                data = r.json()
                if data:
                    return float(data[0][1])  # Open price of the 1-min candle
        except:
            pass
        return None
    
    def get_orderbook(self, limit: int = 50) -> Tuple[List, List]:
        try:
            r = self.client.get(f"{BINANCE_API}/depth", params={
                "symbol": "BTCUSDT", "limit": limit
            })
            if r.status_code == 200:
                d = r.json()
                return d.get("bids", []), d.get("asks", [])
        except:
            pass
        return [], []
    
    def get_agg_trades(self, limit: int = 1000) -> List[Dict]:
        try:
            r = self.client.get(f"{BINANCE_API}/aggTrades", params={
                "symbol": "BTCUSDT", "limit": limit
            })
            if r.status_code == 200:
                return r.json()
        except:
            pass
        return []
    
    def get_5min_volatility(self, lookback: int = 50) -> float:
        """Calculate typical 5-minute price movement (std dev in USD)."""
        candles = self.get_klines("5m", lookback)
        if len(candles) < 10:
            return 50.0  # Default $50
        
        returns = []
        for i in range(1, len(candles)):
            ret = candles[i].close - candles[i-1].close
            returns.append(ret)
        
        if not returns:
            return 50.0
        
        mean = sum(returns) / len(returns)
        var = sum((r - mean)**2 for r in returns) / len(returns)
        return math.sqrt(var) if var > 0 else 50.0


# ===========================================================================
# POLYMARKET DATA FETCHER
# ===========================================================================

class PolymarketFetcher:
    """Fetch live market data from Polymarket for BTC 5-min markets."""
    
    def __init__(self):
        self.client = httpx.Client(timeout=10)
    
    def get_current_market(self, window_start: datetime) -> Optional[MarketData]:
        """Get the Polymarket market for a specific 5-min window."""
        ts = int(window_start.timestamp())
        slug = f"btc-updown-5m-{ts}"
        
        try:
            r = self.client.get(f"{GAMMA_API}/events", params={"slug": slug})
            if r.status_code != 200:
                return None
            
            data = r.json()
            if not data:
                return None
            
            ev = data[0]
            markets = ev.get("markets", [])
            if not markets:
                return None
            
            m = markets[0]
            
            # Parse prices
            prices_str = m.get("outcomePrices", "[0.5, 0.5]")
            prices = json.loads(prices_str) if isinstance(prices_str, str) else prices_str
            up_price = float(prices[0]) if prices else 0.5
            down_price = float(prices[1]) if len(prices) > 1 else 1 - up_price
            
            # Parse CLOB token IDs
            clob_str = m.get("clobTokenIds", "[]")
            clob_ids = json.loads(clob_str) if isinstance(clob_str, str) else clob_str
            up_token = clob_ids[0] if clob_ids else ""
            down_token = clob_ids[1] if len(clob_ids) > 1 else ""
            
            window_end = window_start + timedelta(minutes=5)
            
            return MarketData(
                slug=slug,
                title=ev.get("title", ""),
                up_price=up_price,
                down_price=down_price,
                up_token_id=up_token,
                down_token_id=down_token,
                window_start=window_start,
                window_end=window_end,
                url=f"https://polymarket.com/event/{slug}"
            )
        except Exception as e:
            print(f"  ⚠ Polymarket API error: {e}")
        return None
    
    def get_live_prices(self, market: MarketData) -> Tuple[float, float]:
        """Get latest Up/Down prices from CLOB."""
        try:
            if market.up_token_id:
                r = self.client.get("https://clob.polymarket.com/price",
                    params={"token_id": market.up_token_id, "side": "buy"})
                if r.status_code == 200:
                    up = float(r.json().get("price", market.up_price))
                    return up, 1.0 - up
        except:
            pass
        return market.up_price, market.down_price


# ===========================================================================
# TECHNICAL INDICATORS (compact)
# ===========================================================================

class Ind:
    @staticmethod
    def ema(data, period):
        if not data: return []
        m = 2 / (period + 1)
        r = [data[0]]
        for v in data[1:]:
            r.append((v - r[-1]) * m + r[-1])
        return r
    
    @staticmethod
    def rsi(closes, period=14):
        if len(closes) < period + 1: return 50.0
        deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        gains = [max(d, 0) for d in deltas]
        losses = [max(-d, 0) for d in deltas]
        ag = sum(gains[-period:]) / period
        al = sum(losses[-period:]) / period
        if al == 0: return 100.0
        return 100 - 100 / (1 + ag / al)
    
    @staticmethod
    def macd(closes):
        if len(closes) < 26: return 0, 0, 0
        e12 = Ind.ema(closes, 12)
        e26 = Ind.ema(closes, 26)
        ml = [e12[i] - e26[i] for i in range(len(closes))]
        sl = Ind.ema(ml, 9)
        return ml[-1], sl[-1], ml[-1] - sl[-1]
    
    @staticmethod
    def bollinger_position(closes, period=20):
        """Where is price within Bollinger Bands (0=bottom, 1=top)."""
        if len(closes) < period: return 0.5
        w = closes[-period:]
        mid = sum(w) / period
        var = sum((x - mid)**2 for x in w) / period
        s = math.sqrt(var) if var > 0 else 1
        up = mid + 2 * s
        lo = mid - 2 * s
        if up == lo: return 0.5
        return (closes[-1] - lo) / (up - lo)
    
    @staticmethod
    def stoch_rsi(closes, period=14):
        if len(closes) < period * 2: return 50.0
        rsis = [Ind.rsi(closes[:i], period) for i in range(period, len(closes)+1)]
        if len(rsis) < period: return 50.0
        r = rsis[-period:]
        mn, mx = min(r), max(r)
        if mx == mn: return 50.0
        return (rsis[-1] - mn) / (mx - mn) * 100
    
    @staticmethod
    def adx(candles, period=14):
        if len(candles) < period * 2: return 25.0
        pdm, mdm, trs = [], [], []
        for i in range(1, len(candles)):
            up = candles[i].high - candles[i-1].high
            dn = candles[i-1].low - candles[i].low
            pdm.append(up if up > dn and up > 0 else 0)
            mdm.append(dn if dn > up and dn > 0 else 0)
            trs.append(max(candles[i].high - candles[i].low,
                          abs(candles[i].high - candles[i-1].close),
                          abs(candles[i].low - candles[i-1].close)))
        at = sum(trs[-period:]) / period
        if at == 0: return 0
        ap = sum(pdm[-period:]) / period
        am = sum(mdm[-period:]) / period
        pdi = ap / at * 100
        mdi = am / at * 100
        if pdi + mdi == 0: return 0
        dx = abs(pdi - mdi) / (pdi + mdi) * 100
        return dx, pdi, mdi
    
    @staticmethod
    def momentum_score(closes, periods=[3, 5, 10]):
        """Multi-period momentum score (-1 to +1)."""
        if len(closes) < max(periods) + 1: return 0
        score = 0
        for p in periods:
            change = (closes[-1] - closes[-p-1]) / closes[-p-1]
            score += change
        return score / len(periods)


# ===========================================================================
# ORDER FLOW ANALYZER
# ===========================================================================

class OrderFlowAnalyzer:
    def __init__(self, pe: PriceEngine):
        self.pe = pe
    
    def analyze(self) -> Dict:
        result = {
            "book_imbalance": 0.0,
            "trade_flow": 0.0,
            "score": 0.0,
        }
        
        # Order Book Imbalance
        bids, asks = self.pe.get_orderbook(50)
        if bids and asks:
            bid_vol = sum(float(b[1]) for b in bids)
            ask_vol = sum(float(a[1]) for a in asks)
            total = bid_vol + ask_vol
            if total > 0:
                result["book_imbalance"] = (bid_vol - ask_vol) / total
        
        # Trade Flow (aggressive buyers vs sellers)
        trades = self.pe.get_agg_trades(500)
        if trades:
            buy_vol = 0.0
            sell_vol = 0.0
            for t in trades:
                qty = float(t.get("q", 0))
                if t.get("m"):  # Maker is seller → taker bought
                    sell_vol += qty
                else:
                    buy_vol += qty
            total_trade = buy_vol + sell_vol
            if total_trade > 0:
                result["trade_flow"] = (buy_vol - sell_vol) / total_trade
        
        # Combined score
        result["score"] = result["book_imbalance"] * 3 + result["trade_flow"] * 4
        return result


# ===========================================================================
# 🧠 SMART PREDICTION ENGINE
# ===========================================================================

class SmartPredictor:
    """
    Uses a probability model instead of indicator voting.
    
    Core formula: P(Up) = Φ(D / (σ × √t))
    Where:
      D = current_price - price_to_beat
      σ = 5-min BTC standard deviation
      t = fraction of time remaining (0 to 1)
    
    Then adjusted by momentum, order flow, and market bias.
    """
    
    def __init__(self):
        self.pe = PriceEngine()
        self.pm = PolymarketFetcher()
        self.ofa = OrderFlowAnalyzer(self.pe)
        self._price_to_beat_cache = {}  # slug -> price
    
    def get_price_to_beat(self, window_start: datetime) -> Optional[float]:
        """Get the BTC price at window start (= PRICE TO BEAT)."""
        slug = f"btc-updown-5m-{int(window_start.timestamp())}"
        
        # Check cache
        if slug in self._price_to_beat_cache:
            return self._price_to_beat_cache[slug]
        
        # Get from Binance: open price of 1-min candle at window start
        ts = int(window_start.timestamp())
        price = self.pe.get_btc_price_at_time(ts)
        
        if price:
            self._price_to_beat_cache[slug] = price
            # Clean old entries
            if len(self._price_to_beat_cache) > 50:
                keys = sorted(self._price_to_beat_cache.keys())
                for k in keys[:-20]:
                    del self._price_to_beat_cache[k]
        
        return price
    
    def analyze(self, window_start: datetime) -> Optional[Signal]:
        """Full analysis for a specific 5-min window."""
        now = datetime.now(tz=timezone.utc)
        window_end = window_start + timedelta(minutes=5)
        ts = int(window_start.timestamp())
        slug = f"btc-updown-5m-{ts}"
        
        # ---- 1. Get PRICE TO BEAT ----
        price_to_beat = self.get_price_to_beat(window_start)
        if not price_to_beat:
            print("  ⚠ Cannot get PRICE TO BEAT")
            return None
        
        # ---- 2. Get current BTC price ----
        current_price = self.pe.get_btc_price()
        if not current_price:
            print("  ⚠ Cannot get BTC price")
            return None
        
        # ---- 3. Calculate distance ----
        distance = current_price - price_to_beat  # Positive = above PRICE TO BEAT
        distance_pct = distance / price_to_beat * 100
        
        # ---- 4. Get market data from Polymarket ----
        market = self.pm.get_current_market(window_start)
        market_up_price = 0.5
        market_down_price = 0.5
        url = f"https://polymarket.com/event/{slug}"
        
        if market:
            # Try live CLOB prices first
            live_up, live_down = self.pm.get_live_prices(market)
            market_up_price = live_up
            market_down_price = live_down
            url = market.url
        
        # ---- 5. Calculate statistical probability ----
        time_left = (window_end - now).total_seconds()
        time_fraction = max(time_left / 300.0, 0.01)  # 0 to 1
        
        # 5-min volatility (typical movement in USD)
        sigma_5m = self.pe.get_5min_volatility(50)
        if sigma_5m < 5:
            sigma_5m = 50  # Floor at $50
        
        # Scaled sigma for remaining time
        sigma_remaining = sigma_5m * math.sqrt(time_fraction)
        
        # Statistical P(Up) using normal distribution
        if sigma_remaining > 0:
            z_score = distance / sigma_remaining
            stat_prob_up = norm_cdf(z_score)
        else:
            stat_prob_up = 1.0 if distance > 0 else 0.0
        
        # ---- 6. Momentum Analysis ----
        candles_1m = self.pe.get_klines("1m", 60)
        candles_5m = self.pe.get_klines("5m", 30)
        
        reasons = []
        momentum_adj = 0.0
        
        if candles_1m and len(candles_1m) > 15:
            closes = [c.close for c in candles_1m]
            
            # RSI
            rsi = Ind.rsi(closes, 14)
            rsi_fast = Ind.rsi(closes, 7)
            
            # Short-term momentum
            mom = Ind.momentum_score(closes, [2, 3, 5])
            
            # MACD histogram
            _, _, macd_hist = Ind.macd(closes)
            
            # EMA trend
            ema9 = Ind.ema(closes, 9)
            ema21 = Ind.ema(closes, 21)
            ema_bullish = ema9[-1] > ema21[-1]
            
            # Bollinger position
            bb_pos = Ind.bollinger_position(closes)
            
            # Stochastic RSI
            stoch = Ind.stoch_rsi(closes)
            
            # Recent candles direction (last 3-5)
            recent_up = sum(1 for c in candles_1m[-5:] if c.close > c.open)
            recent_down = 5 - recent_up
            
            # Volume trend
            avg_vol = sum(c.volume for c in candles_1m[-20:-5]) / 15 if len(candles_1m) > 20 else 1
            recent_vol = sum(c.volume for c in candles_1m[-3:]) / 3
            vol_ratio = recent_vol / avg_vol if avg_vol > 0 else 1
            
            # ---- Build momentum adjustment ----
            # Momentum direction
            if mom > 0.0003:  # Bullish momentum
                momentum_adj += 0.05
                reasons.append(f"📈 Momentum UP ({mom*10000:.1f}bps)")
            elif mom < -0.0003:
                momentum_adj -= 0.05
                reasons.append(f"📉 Momentum DOWN ({mom*10000:.1f}bps)")
            
            # Strong momentum
            if mom > 0.001:
                momentum_adj += 0.05
                reasons.append(f"🔥 STRONG bullish momentum")
            elif mom < -0.001:
                momentum_adj -= 0.05
                reasons.append(f"🔥 STRONG bearish momentum")
            
            # RSI extremes
            if rsi < 25:
                momentum_adj += 0.04
                reasons.append(f"RSI oversold ({rsi:.0f})")
            elif rsi > 75:
                momentum_adj -= 0.04
                reasons.append(f"RSI overbought ({rsi:.0f})")
            
            if rsi_fast < 15:
                momentum_adj += 0.03
                reasons.append(f"🔥 Fast RSI extreme low ({rsi_fast:.0f})")
            elif rsi_fast > 85:
                momentum_adj -= 0.03
                reasons.append(f"🔥 Fast RSI extreme high ({rsi_fast:.0f})")
            
            # EMA trend
            if ema_bullish:
                momentum_adj += 0.02
                reasons.append("EMA9 > EMA21 (bullish)")
            else:
                momentum_adj -= 0.02
                reasons.append("EMA9 < EMA21 (bearish)")
            
            # MACD
            if macd_hist > 0:
                momentum_adj += 0.02
            else:
                momentum_adj -= 0.02
            
            # Bollinger extremes
            if bb_pos < 0.1:
                momentum_adj += 0.03
                reasons.append(f"🔥 Bollinger bottom ({bb_pos:.0%})")
            elif bb_pos > 0.9:
                momentum_adj -= 0.03
                reasons.append(f"🔥 Bollinger top ({bb_pos:.0%})")
            
            # Volume confirmation
            if vol_ratio > 2:
                last_dir = 1 if candles_1m[-1].close > candles_1m[-1].open else -1
                momentum_adj += 0.03 * last_dir
                reasons.append(f"Volume spike {vol_ratio:.1f}x")
            
            # Consecutive candles
            if recent_up >= 4:
                momentum_adj += 0.03
                reasons.append(f"{recent_up}/5 green candles")
            elif recent_down >= 4:
                momentum_adj -= 0.03
                reasons.append(f"{recent_down}/5 red candles")
            
            # Stochastic RSI
            if stoch < 10:
                momentum_adj += 0.02
            elif stoch > 90:
                momentum_adj -= 0.02
        
        # ---- 7. Order Flow ----
        of = self.ofa.analyze()
        of_score = of["score"]
        
        if of_score > 2:
            momentum_adj += 0.04
            reasons.append(f"🔥 Strong buy pressure ({of_score:.1f})")
        elif of_score > 0.5:
            momentum_adj += 0.02
            reasons.append(f"Buy pressure ({of_score:.1f})")
        elif of_score < -2:
            momentum_adj -= 0.04
            reasons.append(f"🔥 Strong sell pressure ({of_score:.1f})")
        elif of_score < -0.5:
            momentum_adj -= 0.02
            reasons.append(f"Sell pressure ({of_score:.1f})")
        
        # ---- 8. Multi-timeframe confirmation ----
        if candles_5m and len(candles_5m) > 10:
            cl5 = [c.close for c in candles_5m]
            mom5 = Ind.momentum_score(cl5, [2, 3])
            rsi5 = Ind.rsi(cl5, 14)
            
            if mom5 > 0.0005 and rsi5 > 50:
                momentum_adj += 0.03
                reasons.append("5m timeframe bullish")
            elif mom5 < -0.0005 and rsi5 < 50:
                momentum_adj -= 0.03
                reasons.append("5m timeframe bearish")
        
        # ---- 9. COMBINE: Statistical + Momentum + Market ----
        # Base: statistical probability
        prob_up = stat_prob_up
        
        # Add momentum adjustment
        prob_up = max(0.01, min(0.99, prob_up + momentum_adj))
        
        # Factor in market bias (weight: 20%)
        # The market has real money behind it — don't ignore it
        market_weight = 0.2
        prob_up = prob_up * (1 - market_weight) + market_up_price * market_weight
        
        # ---- 10. Determine direction and confidence ----
        if prob_up >= 0.5:
            direction = "UP"
            confidence = prob_up * 100
        else:
            direction = "DOWN"
            confidence = (1 - prob_up) * 100
        
        # ---- 11. Time-based adjustments ----
        # More time left = more uncertainty
        if time_left > 240:  # > 4 min left
            confidence *= 0.90  # 10% penalty — too early
            reasons.append(f"⏳ Early in window ({time_left:.0f}s left)")
        elif time_left < 60:  # < 1 min left
            # Late in window: if price is on our side, boost confidence
            if (direction == "UP" and distance > 0) or (direction == "DOWN" and distance < 0):
                confidence = min(98, confidence * 1.1)
                reasons.append(f"⏰ Late + price on our side ({time_left:.0f}s)")
        
        # ---- 12. KEY REASON: Distance from PRICE TO BEAT ----
        if direction == "UP":
            if distance > sigma_5m * 0.5:
                reasons.insert(0, f"🔥🔥 ${distance:+.2f} above PRICE TO BEAT (strong)")
            elif distance > 0:
                reasons.insert(0, f"📊 ${distance:+.2f} above PRICE TO BEAT")
            else:
                reasons.insert(0, f"⚠ ${distance:+.2f} BELOW PRICE TO BEAT (risky)")
        else:
            if distance < -sigma_5m * 0.5:
                reasons.insert(0, f"🔥🔥 ${distance:+.2f} below PRICE TO BEAT (strong)")
            elif distance < 0:
                reasons.insert(0, f"📊 ${distance:+.2f} below PRICE TO BEAT")
            else:
                reasons.insert(0, f"⚠ ${distance:+.2f} ABOVE PRICE TO BEAT (risky)")
        
        # Add market info
        reasons.append(f"Market: Up {market_up_price:.0%} / Down {market_down_price:.0%}")
        reasons.append(f"σ(5m) = ${sigma_5m:.0f} | Z = {z_score:.2f}")
        
        # ---- 13. Determine tier ----
        if confidence >= 90:
            tier = "SNIPER"
        elif confidence >= 80:
            tier = "SIGNAL"
        elif confidence >= 70:
            tier = "WATCH"
        else:
            tier = "SKIP"
        
        return Signal(
            direction=direction,
            confidence=round(confidence, 1),
            tier=tier,
            reasons=reasons,
            btc_price=current_price,
            price_to_beat=price_to_beat,
            distance_usd=distance,
            market_bias=market_up_price,
            window_start=window_start,
            window_end=window_end,
            time_left=int(time_left),
            slug=slug,
            url=url,
        )


# ===========================================================================
# TELEGRAM
# ===========================================================================

class TelegramAlerter:
    def __init__(self):
        self.client = httpx.Client(timeout=10)
        self.sent = set()
    
    def send(self, sig: Signal):
        key = f"{sig.slug}_{sig.direction}"
        if key in self.sent:
            return
        if sig.confidence < MIN_CONFIDENCE:
            return
        
        self.sent.add(key)
        
        tier_map = {
            "SNIPER": "🎯🔥 SNIPER SHOT",
            "SIGNAL": "🟢 STRONG SIGNAL",
            "WATCH":  "🟡 WATCH",
        }
        tier_label = tier_map.get(sig.tier, sig.tier)
        dir_emoji = "⬆️ UP" if sig.direction == "UP" else "⬇️ DOWN"
        
        # Confidence bar
        filled = int(sig.confidence / 10)
        bar = "█" * filled + "░" * (10 - filled)
        
        # Top reasons
        reason_lines = "\n".join(f"  • {r}" for r in sig.reasons[:8])
        
        # Time
        ws_et = sig.window_start - timedelta(hours=5)
        we_et = sig.window_end - timedelta(hours=5)
        
        msg = f"""{tier_label}

{dir_emoji}  |  Confidence: {sig.confidence}%
[{bar}]

⏰ {ws_et.strftime('%I:%M')}-{we_et.strftime('%I:%M %p')} ET
⏱ {sig.time_left}s remaining

💰 BTC: ${sig.btc_price:,.2f}
🎯 PRICE TO BEAT: ${sig.price_to_beat:,.2f}
📐 Distance: ${sig.distance_usd:+,.2f}
📊 Market Bias: Up {sig.market_bias:.0%}

📋 Analysis:
{reason_lines}

🔗 {sig.url}

⚡ Buy {sig.direction} on Polymarket"""
        
        for cid in TELEGRAM_CHAT_IDS:
            try:
                self.client.post(
                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                    json={"chat_id": cid, "text": msg}
                )
            except Exception as e:
                print(f"  ⚠ TG error: {e}")
        
        print(f"  📢 [{sig.tier}] {sig.direction} ({sig.confidence}%) sent to Telegram")
    
    def cleanup(self):
        if len(self.sent) > 500:
            self.sent = set(list(self.sent)[-50:])
    
    def already_sent(self, slug: str) -> bool:
        return any(slug in k for k in self.sent)


# ===========================================================================
# MAIN LOOP
# ===========================================================================

def get_current_window() -> Tuple[datetime, datetime]:
    """Get the current active 5-min window."""
    now = datetime.now(tz=timezone.utc)
    minute = now.minute
    cur_5 = (minute // 5) * 5
    ws = now.replace(minute=cur_5, second=0, microsecond=0)
    we = ws + timedelta(minutes=5)
    return ws, we


def main():
    print("=" * 60)
    print("  🎯 BTC 5-MIN PREDICTOR v2 — SMART PROBABILITY MODEL")
    print("  Based on: Distance from PRICE TO BEAT + σ + Momentum")
    print("  + Polymarket Bias + Order Flow")
    print("  Min confidence: {}%".format(MIN_CONFIDENCE))
    print("=" * 60)
    
    predictor = SmartPredictor()
    alerter = TelegramAlerter()
    scan = 0
    stats = {"signals": 0, "skips": 0, "too_early": 0}
    
    while True:
        try:
            scan += 1
            now = datetime.now(tz=timezone.utc)
            ws, we = get_current_window()
            ts = int(ws.timestamp())
            slug = f"btc-updown-5m-{ts}"
            
            elapsed = (now - ws).total_seconds()
            remaining = (we - now).total_seconds()
            
            print(f"\n  [{now.strftime('%H:%M:%S')} UTC] Scan #{scan}")
            print(f"  Window: {ws.strftime('%H:%M')}-{we.strftime('%H:%M')} | "
                  f"Elapsed: {elapsed:.0f}s | Left: {remaining:.0f}s")
            
            # Check if we should analyze this window
            if elapsed < SIGNAL_WINDOW_START:
                wait = SIGNAL_WINDOW_START - elapsed
                print(f"  ⏳ Too early. Waiting {wait:.0f}s for window to develop...")
                stats["too_early"] += 1
                time.sleep(min(wait, SCAN_INTERVAL))
                continue
            
            if elapsed > SIGNAL_WINDOW_END:
                print(f"  ⏭ Window too old ({elapsed:.0f}s elapsed). Waiting for next...")
                next_ws = ws + timedelta(minutes=5)
                wait = (next_ws - now).total_seconds() + SIGNAL_WINDOW_START
                time.sleep(min(max(wait, 1), 30))
                continue
            
            if alerter.already_sent(slug):
                print(f"  ✅ Already signaled this window")
                next_ws = ws + timedelta(minutes=5)
                wait = (next_ws - now).total_seconds() + SIGNAL_WINDOW_START
                time.sleep(min(max(wait, 1), 30))
                continue
            
            # ---- FULL ANALYSIS ----
            print(f"  🔍 Analyzing...")
            sig = predictor.analyze(ws)
            
            if not sig:
                print(f"  ⚠ Analysis failed")
                time.sleep(SCAN_INTERVAL)
                continue
            
            print(f"  📊 Direction: {sig.direction}")
            print(f"  📊 Confidence: {sig.confidence}%")
            print(f"  📊 Tier: {sig.tier}")
            print(f"  💰 BTC: ${sig.btc_price:,.2f}")
            print(f"  🎯 PTB: ${sig.price_to_beat:,.2f}")
            print(f"  📐 Distance: ${sig.distance_usd:+,.2f}")
            print(f"  📊 Market: Up {sig.market_bias:.0%}")
            
            for r in sig.reasons[:5]:
                print(f"      • {r}")
            
            if sig.tier != "SKIP":
                alerter.send(sig)
                stats["signals"] += 1
                print(f"  ✅ SIGNAL SENT!")
            else:
                stats["skips"] += 1
                print(f"  ⏭ SKIPPED (confidence {sig.confidence}% < {MIN_CONFIDENCE}%)")
            
            total = stats["signals"] + stats["skips"]
            if total > 0:
                rate = stats["signals"] / total * 100
                print(f"  📈 Stats: {stats['signals']} signals / {total} analyzed ({rate:.0f}% signal rate)")
            
            alerter.cleanup()
            
            # If already signaled or skipped, wait for next window
            if sig.tier != "SKIP":
                next_ws = ws + timedelta(minutes=5)
                wait = (next_ws - now).total_seconds() + SIGNAL_WINDOW_START
                time.sleep(min(max(wait, 1), 30))
            else:
                # Retry in this window (maybe conditions improve)
                time.sleep(SCAN_INTERVAL)
            
        except KeyboardInterrupt:
            print("\n  Stopped")
            break
        except Exception as e:
            print(f"  ❌ Error: {e}")
            traceback.print_exc()
            time.sleep(10)


if __name__ == "__main__":
    main()
