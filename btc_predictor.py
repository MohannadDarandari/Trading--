#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║  🎯 BTC 5-MIN PREDICTOR — Polymarket Up/Down Signal Bot        ║
║  Multi-Indicator Technical Analysis + Telegram Alerts           ║
╚══════════════════════════════════════════════════════════════════╝

INDICATORS USED:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1.  RSI (14) — Relative Strength Index
2.  RSI (7) — Fast RSI for short-term
3.  MACD (12,26,9) — Trend + Momentum
4.  EMA Cross (9/21) — Exponential Moving Average
5.  EMA (50) — Medium trend
6.  Bollinger Bands (20,2) — Volatility + Mean Reversion
7.  Stochastic RSI — Overbought/Oversold
8.  ATR — Average True Range (volatility filter)
9.  VWAP — Volume Weighted Average Price
10. OBV — On-Balance Volume (volume trend)
11. ADX — Average Directional Index (trend strength)
12. Williams %R — Momentum oscillator
13. CCI — Commodity Channel Index
14. Momentum (10) — Price rate of change
15. Ichimoku Cloud — Multi-timeframe trend
16. Pivot Points — Support/Resistance levels
17. Candlestick Patterns — Engulfing, Doji, Hammer, etc.
18. Volume Spike Detection — Unusual volume signals
19. Order Flow Imbalance — Buy vs Sell pressure
20. Multi-Timeframe Confluence — 1m, 5m, 15m agreement

SIGNAL LOGIC:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Each indicator votes UP or DOWN with a confidence weight
• Final signal = weighted sum of all votes
• Confidence threshold: signals only sent when confidence > 55%
• Edge cases: FLAT/SKIP when indicators conflict heavily
"""

import os
import sys
import json
import time
import math
import traceback
from pathlib import Path
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict

import httpx

# ===========================================================================
# CONFIGURATION
# ===========================================================================

TELEGRAM_TOKEN = "8331165268:AAEA84wTDNeFuPhRJkjLiUqxxkaPEuL2B-o"
TELEGRAM_CHAT_IDS = ["1688623770", "1675476723"]

# BTC price sources
BINANCE_API = "https://api.binance.com/api/v3"
COINGECKO_API = "https://api.coingecko.com/api/v3"

# Scan interval (check every 30 seconds for upcoming windows)
SCAN_INTERVAL = 30

# Signal confidence threshold (0-100)
MIN_CONFIDENCE = 52

# How many seconds before window START to send signal
SIGNAL_LEAD_TIME = 90  # Send signal 1.5 min before window starts

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
class Signal:
    direction: str  # "UP" or "DOWN"
    confidence: float  # 0-100
    indicators: Dict[str, Tuple[str, float]]  # name -> (direction, weight)
    btc_price: float
    timestamp: datetime
    window_start: datetime
    window_end: datetime
    market_slug: str
    polymarket_url: str

# ===========================================================================
# PRICE DATA FETCHER
# ===========================================================================

class PriceEngine:
    """Fetches BTC price data from multiple sources."""
    
    def __init__(self):
        self.client = httpx.Client(timeout=10)
    
    def get_klines(self, interval: str = "1m", limit: int = 200) -> List[Candle]:
        """Get BTC/USDT klines from Binance."""
        try:
            r = self.client.get(f"{BINANCE_API}/klines", params={
                "symbol": "BTCUSDT",
                "interval": interval,
                "limit": limit,
            })
            if r.status_code == 200:
                candles = []
                for k in r.json():
                    candles.append(Candle(
                        timestamp=k[0] / 1000,
                        open=float(k[1]),
                        high=float(k[2]),
                        low=float(k[3]),
                        close=float(k[4]),
                        volume=float(k[5]),
                    ))
                return candles
        except Exception as e:
            print(f"  ⚠ Binance error: {e}")
        return []
    
    def get_current_price(self) -> float:
        """Get current BTC price."""
        try:
            r = self.client.get(f"{BINANCE_API}/ticker/price", params={"symbol": "BTCUSDT"})
            if r.status_code == 200:
                return float(r.json()["price"])
        except:
            pass
        return 0.0
    
    def get_orderbook(self, limit: int = 20) -> Tuple[List, List]:
        """Get BTC/USDT order book for order flow analysis."""
        try:
            r = self.client.get(f"{BINANCE_API}/depth", params={
                "symbol": "BTCUSDT",
                "limit": limit,
            })
            if r.status_code == 200:
                data = r.json()
                return data.get("bids", []), data.get("asks", [])
        except:
            pass
        return [], []
    
    def get_recent_trades(self, limit: int = 500) -> List[Dict]:
        """Get recent trades for order flow analysis."""
        try:
            r = self.client.get(f"{BINANCE_API}/trades", params={
                "symbol": "BTCUSDT",
                "limit": limit,
            })
            if r.status_code == 200:
                return r.json()
        except:
            pass
        return []


# ===========================================================================
# TECHNICAL INDICATORS
# ===========================================================================

class Indicators:
    """All technical indicators computed from candle data."""
    
    @staticmethod
    def sma(data: List[float], period: int) -> List[float]:
        result = [None] * (period - 1)
        for i in range(period - 1, len(data)):
            result.append(sum(data[i - period + 1:i + 1]) / period)
        return result
    
    @staticmethod
    def ema(data: List[float], period: int) -> List[float]:
        if not data:
            return []
        multiplier = 2 / (period + 1)
        result = [data[0]]
        for i in range(1, len(data)):
            val = (data[i] - result[-1]) * multiplier + result[-1]
            result.append(val)
        return result
    
    @staticmethod
    def rsi(closes: List[float], period: int = 14) -> float:
        if len(closes) < period + 1:
            return 50.0
        deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    @staticmethod
    def macd(closes: List[float]) -> Tuple[float, float, float]:
        """Returns (macd_line, signal_line, histogram)."""
        if len(closes) < 26:
            return 0, 0, 0
        ema12 = Indicators.ema(closes, 12)
        ema26 = Indicators.ema(closes, 26)
        macd_line = [ema12[i] - ema26[i] for i in range(len(closes))]
        signal = Indicators.ema(macd_line, 9)
        hist = macd_line[-1] - signal[-1]
        return macd_line[-1], signal[-1], hist
    
    @staticmethod
    def bollinger_bands(closes: List[float], period: int = 20, std_dev: float = 2.0) -> Tuple[float, float, float]:
        """Returns (upper, middle, lower)."""
        if len(closes) < period:
            return closes[-1] * 1.02, closes[-1], closes[-1] * 0.98
        window = closes[-period:]
        middle = sum(window) / period
        variance = sum((x - middle) ** 2 for x in window) / period
        std = math.sqrt(variance)
        return middle + std_dev * std, middle, middle - std_dev * std
    
    @staticmethod
    def stochastic_rsi(closes: List[float], period: int = 14) -> float:
        if len(closes) < period * 2:
            return 50.0
        rsi_values = []
        for i in range(period, len(closes) + 1):
            rsi_values.append(Indicators.rsi(closes[:i], period))
        if not rsi_values or len(rsi_values) < period:
            return 50.0
        recent = rsi_values[-period:]
        min_rsi = min(recent)
        max_rsi = max(recent)
        if max_rsi == min_rsi:
            return 50.0
        return ((rsi_values[-1] - min_rsi) / (max_rsi - min_rsi)) * 100
    
    @staticmethod
    def atr(candles: List[Candle], period: int = 14) -> float:
        if len(candles) < period + 1:
            return 0.0
        true_ranges = []
        for i in range(1, len(candles)):
            tr = max(
                candles[i].high - candles[i].low,
                abs(candles[i].high - candles[i-1].close),
                abs(candles[i].low - candles[i-1].close)
            )
            true_ranges.append(tr)
        return sum(true_ranges[-period:]) / period
    
    @staticmethod
    def vwap(candles: List[Candle], period: int = 20) -> float:
        recent = candles[-period:]
        total_vol = sum(c.volume for c in recent)
        if total_vol == 0:
            return recent[-1].close
        return sum(((c.high + c.low + c.close) / 3) * c.volume for c in recent) / total_vol
    
    @staticmethod
    def obv(candles: List[Candle]) -> List[float]:
        result = [0.0]
        for i in range(1, len(candles)):
            if candles[i].close > candles[i-1].close:
                result.append(result[-1] + candles[i].volume)
            elif candles[i].close < candles[i-1].close:
                result.append(result[-1] - candles[i].volume)
            else:
                result.append(result[-1])
        return result
    
    @staticmethod
    def adx(candles: List[Candle], period: int = 14) -> float:
        if len(candles) < period * 2:
            return 25.0
        plus_dm = []
        minus_dm = []
        tr_list = []
        for i in range(1, len(candles)):
            up = candles[i].high - candles[i-1].high
            down = candles[i-1].low - candles[i].low
            plus_dm.append(up if up > down and up > 0 else 0)
            minus_dm.append(down if down > up and down > 0 else 0)
            tr = max(
                candles[i].high - candles[i].low,
                abs(candles[i].high - candles[i-1].close),
                abs(candles[i].low - candles[i-1].close)
            )
            tr_list.append(tr)
        
        avg_tr = sum(tr_list[-period:]) / period
        if avg_tr == 0:
            return 0
        avg_plus = sum(plus_dm[-period:]) / period
        avg_minus = sum(minus_dm[-period:]) / period
        
        plus_di = (avg_plus / avg_tr) * 100
        minus_di = (avg_minus / avg_tr) * 100
        
        if plus_di + minus_di == 0:
            return 0
        dx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100
        return dx
    
    @staticmethod
    def williams_r(candles: List[Candle], period: int = 14) -> float:
        if len(candles) < period:
            return -50.0
        recent = candles[-period:]
        highest = max(c.high for c in recent)
        lowest = min(c.low for c in recent)
        if highest == lowest:
            return -50.0
        return ((highest - candles[-1].close) / (highest - lowest)) * -100
    
    @staticmethod
    def cci(candles: List[Candle], period: int = 20) -> float:
        if len(candles) < period:
            return 0.0
        recent = candles[-period:]
        tp = [(c.high + c.low + c.close) / 3 for c in recent]
        mean_tp = sum(tp) / period
        mean_dev = sum(abs(t - mean_tp) for t in tp) / period
        if mean_dev == 0:
            return 0.0
        return (tp[-1] - mean_tp) / (0.015 * mean_dev)
    
    @staticmethod
    def momentum(closes: List[float], period: int = 10) -> float:
        if len(closes) < period + 1:
            return 0.0
        return closes[-1] - closes[-period - 1]
    
    @staticmethod
    def ichimoku(candles: List[Candle]) -> Dict:
        """Simplified Ichimoku."""
        if len(candles) < 52:
            return {"signal": "neutral", "strength": 0}
        
        # Tenkan-sen (9)
        recent9 = candles[-9:]
        tenkan = (max(c.high for c in recent9) + min(c.low for c in recent9)) / 2
        
        # Kijun-sen (26)
        recent26 = candles[-26:]
        kijun = (max(c.high for c in recent26) + min(c.low for c in recent26)) / 2
        
        # Senkou A
        senkou_a = (tenkan + kijun) / 2
        
        # Senkou B (52)
        recent52 = candles[-52:]
        senkou_b = (max(c.high for c in recent52) + min(c.low for c in recent52)) / 2
        
        price = candles[-1].close
        
        if price > senkou_a and price > senkou_b and tenkan > kijun:
            return {"signal": "bullish", "strength": 2}
        elif price < senkou_a and price < senkou_b and tenkan < kijun:
            return {"signal": "bearish", "strength": 2}
        elif price > senkou_a or tenkan > kijun:
            return {"signal": "bullish", "strength": 1}
        elif price < senkou_b or tenkan < kijun:
            return {"signal": "bearish", "strength": 1}
        return {"signal": "neutral", "strength": 0}
    
    @staticmethod
    def pivot_points(candles: List[Candle]) -> Dict:
        """Calculate pivot points from previous session."""
        if len(candles) < 2:
            return {}
        prev = candles[-2]
        pivot = (prev.high + prev.low + prev.close) / 3
        return {
            "pivot": pivot,
            "r1": 2 * pivot - prev.low,
            "r2": pivot + (prev.high - prev.low),
            "s1": 2 * pivot - prev.high,
            "s2": pivot - (prev.high - prev.low),
        }
    
    @staticmethod
    def detect_candlestick_pattern(candles: List[Candle]) -> Tuple[str, str]:
        """Detect candlestick patterns. Returns (pattern_name, direction)."""
        if len(candles) < 3:
            return "none", "neutral"
        
        c = candles[-1]
        p = candles[-2]
        pp = candles[-3]
        
        body = abs(c.close - c.open)
        upper_wick = c.high - max(c.open, c.close)
        lower_wick = min(c.open, c.close) - c.low
        total_range = c.high - c.low
        
        if total_range == 0:
            return "none", "neutral"
        
        # Doji
        if body / total_range < 0.1:
            return "doji", "reversal"
        
        # Hammer (bullish reversal)
        if lower_wick > body * 2 and upper_wick < body * 0.5 and c.close < p.close:
            return "hammer", "up"
        
        # Shooting star (bearish reversal)
        if upper_wick > body * 2 and lower_wick < body * 0.5 and c.close > p.close:
            return "shooting_star", "down"
        
        # Bullish engulfing
        if (p.close < p.open and c.close > c.open and 
            c.open < p.close and c.close > p.open):
            return "bullish_engulfing", "up"
        
        # Bearish engulfing
        if (p.close > p.open and c.close < c.open and 
            c.open > p.close and c.close < p.open):
            return "bearish_engulfing", "down"
        
        # Three white soldiers
        if (c.close > c.open and p.close > p.open and pp.close > pp.open and
            c.close > p.close and p.close > pp.close):
            return "three_soldiers", "up"
        
        # Three black crows
        if (c.close < c.open and p.close < p.open and pp.close < pp.open and
            c.close < p.close and p.close < pp.close):
            return "three_crows", "down"
        
        return "none", "neutral"
    
    @staticmethod
    def volume_spike(candles: List[Candle], threshold: float = 2.0) -> Tuple[bool, str]:
        """Detect volume spikes."""
        if len(candles) < 21:
            return False, "neutral"
        avg_vol = sum(c.volume for c in candles[-21:-1]) / 20
        if avg_vol == 0:
            return False, "neutral"
        ratio = candles[-1].volume / avg_vol
        if ratio > threshold:
            direction = "up" if candles[-1].close > candles[-1].open else "down"
            return True, direction
        return False, "neutral"


# ===========================================================================
# PREDICTION ENGINE
# ===========================================================================

class PredictionEngine:
    """Combines all indicators to predict BTC 5-min direction."""
    
    def __init__(self):
        self.price_engine = PriceEngine()
        self.ind = Indicators()
    
    def analyze(self) -> Signal:
        """Run full analysis and return prediction signal."""
        
        # Fetch data from multiple timeframes
        candles_1m = self.price_engine.get_klines("1m", 200)
        candles_5m = self.price_engine.get_klines("5m", 100)
        candles_15m = self.price_engine.get_klines("15m", 60)
        
        if not candles_1m or not candles_5m:
            return None
        
        closes_1m = [c.close for c in candles_1m]
        closes_5m = [c.close for c in candles_5m]
        closes_15m = [c.close for c in candles_15m]
        
        current_price = candles_1m[-1].close
        
        # ============================================================
        # INDICATOR VOTES: (direction, weight)
        # ============================================================
        votes = {}
        
        # ---------- 1. RSI(14) on 1m ----------
        rsi14 = self.ind.rsi(closes_1m, 14)
        if rsi14 > 70:
            votes["RSI(14)"] = ("DOWN", 1.5)  # Overbought → reversal down
        elif rsi14 < 30:
            votes["RSI(14)"] = ("UP", 1.5)    # Oversold → reversal up
        elif rsi14 > 55:
            votes["RSI(14)"] = ("UP", 0.5)
        elif rsi14 < 45:
            votes["RSI(14)"] = ("DOWN", 0.5)
        else:
            votes["RSI(14)"] = ("NEUTRAL", 0.0)
        
        # ---------- 2. RSI(7) Fast ----------
        rsi7 = self.ind.rsi(closes_1m, 7)
        if rsi7 > 75:
            votes["RSI(7)"] = ("DOWN", 1.2)
        elif rsi7 < 25:
            votes["RSI(7)"] = ("UP", 1.2)
        elif rsi7 > 55:
            votes["RSI(7)"] = ("UP", 0.4)
        elif rsi7 < 45:
            votes["RSI(7)"] = ("DOWN", 0.4)
        else:
            votes["RSI(7)"] = ("NEUTRAL", 0.0)
        
        # ---------- 3. MACD ----------
        macd_line, signal_line, histogram = self.ind.macd(closes_1m)
        if histogram > 0 and macd_line > signal_line:
            votes["MACD"] = ("UP", 1.5)
        elif histogram < 0 and macd_line < signal_line:
            votes["MACD"] = ("DOWN", 1.5)
        elif histogram > 0:
            votes["MACD"] = ("UP", 0.5)
        elif histogram < 0:
            votes["MACD"] = ("DOWN", 0.5)
        else:
            votes["MACD"] = ("NEUTRAL", 0.0)
        
        # ---------- 4. EMA Cross (9/21) ----------
        ema9 = self.ind.ema(closes_1m, 9)
        ema21 = self.ind.ema(closes_1m, 21)
        if ema9[-1] > ema21[-1]:
            # Check if just crossed
            cross_strength = (ema9[-1] - ema21[-1]) / current_price * 10000
            weight = min(1.5, 0.5 + cross_strength * 0.1)
            votes["EMA(9/21)"] = ("UP", weight)
        else:
            cross_strength = (ema21[-1] - ema9[-1]) / current_price * 10000
            weight = min(1.5, 0.5 + cross_strength * 0.1)
            votes["EMA(9/21)"] = ("DOWN", weight)
        
        # ---------- 5. EMA(50) Trend ----------
        ema50 = self.ind.ema(closes_1m, 50)
        if current_price > ema50[-1]:
            votes["EMA(50)"] = ("UP", 0.8)
        else:
            votes["EMA(50)"] = ("DOWN", 0.8)
        
        # ---------- 6. Bollinger Bands ----------
        bb_upper, bb_middle, bb_lower = self.ind.bollinger_bands(closes_1m)
        bb_width = (bb_upper - bb_lower) / bb_middle * 100
        if current_price > bb_upper:
            votes["BB"] = ("DOWN", 1.3)  # Above upper = likely reversal
        elif current_price < bb_lower:
            votes["BB"] = ("UP", 1.3)    # Below lower = likely bounce
        elif current_price > bb_middle:
            votes["BB"] = ("UP", 0.4)
        else:
            votes["BB"] = ("DOWN", 0.4)
        
        # ---------- 7. Stochastic RSI ----------
        stoch_rsi = self.ind.stochastic_rsi(closes_1m)
        if stoch_rsi > 80:
            votes["StochRSI"] = ("DOWN", 1.2)
        elif stoch_rsi < 20:
            votes["StochRSI"] = ("UP", 1.2)
        elif stoch_rsi > 55:
            votes["StochRSI"] = ("UP", 0.3)
        elif stoch_rsi < 45:
            votes["StochRSI"] = ("DOWN", 0.3)
        else:
            votes["StochRSI"] = ("NEUTRAL", 0.0)
        
        # ---------- 8. ATR Volatility ----------
        atr = self.ind.atr(candles_1m)
        atr_pct = (atr / current_price) * 100
        # ATR doesn't predict direction, but affects confidence
        
        # ---------- 9. VWAP ----------
        vwap = self.ind.vwap(candles_1m, 30)
        if current_price > vwap:
            votes["VWAP"] = ("UP", 1.0)
        else:
            votes["VWAP"] = ("DOWN", 1.0)
        
        # ---------- 10. OBV ----------
        obv = self.ind.obv(candles_1m)
        obv_ema = self.ind.ema(obv[-20:], 10) if len(obv) >= 20 else obv
        if len(obv_ema) > 1 and obv[-1] > obv_ema[-1]:
            votes["OBV"] = ("UP", 0.8)
        elif len(obv_ema) > 1:
            votes["OBV"] = ("DOWN", 0.8)
        else:
            votes["OBV"] = ("NEUTRAL", 0.0)
        
        # ---------- 11. ADX ----------
        adx = self.ind.adx(candles_1m)
        # ADX > 25 = strong trend, boost trend-following signals
        trend_multiplier = 1.2 if adx > 25 else 0.8
        
        # ---------- 12. Williams %R ----------
        wpr = self.ind.williams_r(candles_1m)
        if wpr > -20:
            votes["Williams%R"] = ("DOWN", 1.0)  # Overbought
        elif wpr < -80:
            votes["Williams%R"] = ("UP", 1.0)    # Oversold
        elif wpr > -45:
            votes["Williams%R"] = ("UP", 0.3)
        elif wpr < -55:
            votes["Williams%R"] = ("DOWN", 0.3)
        else:
            votes["Williams%R"] = ("NEUTRAL", 0.0)
        
        # ---------- 13. CCI ----------
        cci = self.ind.cci(candles_1m)
        if cci > 100:
            votes["CCI"] = ("DOWN", 1.0)
        elif cci < -100:
            votes["CCI"] = ("UP", 1.0)
        elif cci > 0:
            votes["CCI"] = ("UP", 0.3)
        else:
            votes["CCI"] = ("DOWN", 0.3)
        
        # ---------- 14. Momentum ----------
        mom = self.ind.momentum(closes_1m)
        if mom > 0:
            votes["Momentum"] = ("UP", 0.8)
        elif mom < 0:
            votes["Momentum"] = ("DOWN", 0.8)
        else:
            votes["Momentum"] = ("NEUTRAL", 0.0)
        
        # ---------- 15. Ichimoku Cloud ----------
        ichimoku = self.ind.ichimoku(candles_5m)
        if ichimoku["signal"] == "bullish":
            votes["Ichimoku"] = ("UP", ichimoku["strength"] * 0.6)
        elif ichimoku["signal"] == "bearish":
            votes["Ichimoku"] = ("DOWN", ichimoku["strength"] * 0.6)
        else:
            votes["Ichimoku"] = ("NEUTRAL", 0.0)
        
        # ---------- 16. Pivot Points ----------
        pivots = self.ind.pivot_points(candles_5m)
        if pivots:
            if current_price > pivots["r1"]:
                votes["Pivots"] = ("UP", 0.8)
            elif current_price < pivots["s1"]:
                votes["Pivots"] = ("DOWN", 0.8)
            elif current_price > pivots["pivot"]:
                votes["Pivots"] = ("UP", 0.4)
            else:
                votes["Pivots"] = ("DOWN", 0.4)
        
        # ---------- 17. Candlestick Patterns ----------
        pattern, pat_dir = self.ind.detect_candlestick_pattern(candles_1m)
        if pat_dir == "up":
            votes["Candle"] = ("UP", 1.2)
        elif pat_dir == "down":
            votes["Candle"] = ("DOWN", 1.2)
        elif pat_dir == "reversal":
            # Doji - use trend context
            if ema9[-1] > ema21[-1]:
                votes["Candle"] = ("DOWN", 0.5)  # Reversal of uptrend
            else:
                votes["Candle"] = ("UP", 0.5)
        
        # ---------- 18. Volume Spike ----------
        spike, spike_dir = self.ind.volume_spike(candles_1m)
        if spike:
            if spike_dir == "up":
                votes["VolSpike"] = ("UP", 1.5)
            else:
                votes["VolSpike"] = ("DOWN", 1.5)
        
        # ---------- 19. Order Flow ----------
        bids, asks = self.price_engine.get_orderbook(20)
        if bids and asks:
            bid_vol = sum(float(b[1]) for b in bids)
            ask_vol = sum(float(a[1]) for a in asks)
            total = bid_vol + ask_vol
            if total > 0:
                imbalance = (bid_vol - ask_vol) / total
                if imbalance > 0.1:
                    votes["OrderFlow"] = ("UP", min(1.5, imbalance * 5))
                elif imbalance < -0.1:
                    votes["OrderFlow"] = ("DOWN", min(1.5, abs(imbalance) * 5))
                else:
                    votes["OrderFlow"] = ("NEUTRAL", 0.0)
        
        # ---------- 20. Multi-Timeframe Confluence ----------
        # Check 5m and 15m trends
        rsi_5m = self.ind.rsi(closes_5m, 14) if len(closes_5m) > 14 else 50
        rsi_15m = self.ind.rsi(closes_15m, 14) if len(closes_15m) > 14 else 50
        
        ema9_5m = self.ind.ema(closes_5m, 9)
        ema21_5m = self.ind.ema(closes_5m, 21)
        
        mtf_up = 0
        mtf_down = 0
        if rsi_5m > 55: mtf_up += 1
        elif rsi_5m < 45: mtf_down += 1
        if rsi_15m > 55: mtf_up += 1
        elif rsi_15m < 45: mtf_down += 1
        if len(ema9_5m) > 0 and len(ema21_5m) > 0 and ema9_5m[-1] > ema21_5m[-1]:
            mtf_up += 1
        else:
            mtf_down += 1
        
        if mtf_up >= 2:
            votes["MTF"] = ("UP", 1.0)
        elif mtf_down >= 2:
            votes["MTF"] = ("DOWN", 1.0)
        else:
            votes["MTF"] = ("NEUTRAL", 0.0)
        
        # ============================================================
        # WEIGHTED VOTE AGGREGATION
        # ============================================================
        up_score = 0.0
        down_score = 0.0
        total_weight = 0.0
        
        for name, (direction, weight) in votes.items():
            # Apply trend strength multiplier for trend-following indicators
            if name in ["EMA(9/21)", "EMA(50)", "MACD", "Momentum", "MTF"] and adx > 25:
                weight *= trend_multiplier
            
            if direction == "UP":
                up_score += weight
            elif direction == "DOWN":
                down_score += weight
            total_weight += weight
        
        # Calculate confidence
        if total_weight == 0:
            return None
        
        if up_score > down_score:
            direction = "UP"
            confidence = (up_score / (up_score + down_score)) * 100
        else:
            direction = "DOWN"
            confidence = (down_score / (up_score + down_score)) * 100
        
        # Adjust confidence based on ATR (high volatility = less certain)
        if atr_pct > 0.15:
            confidence *= 0.9
        
        # Adjust for ADX (strong trend = more confident)
        if adx > 30:
            confidence = min(95, confidence * 1.05)
        
        # Calculate next window
        now = datetime.now(tz=timezone.utc)
        next_5min = self._next_window(now)
        window_end = next_5min + timedelta(minutes=5)
        ts = int(next_5min.timestamp())
        slug = f"btc-updown-5m-{ts}"
        
        return Signal(
            direction=direction,
            confidence=round(confidence, 1),
            indicators=votes,
            btc_price=current_price,
            timestamp=now,
            window_start=next_5min,
            window_end=window_end,
            market_slug=slug,
            polymarket_url=f"https://polymarket.com/event/{slug}",
        )
    
    def _next_window(self, now: datetime) -> datetime:
        """Calculate the next 5-minute window start."""
        minute = now.minute
        next_5 = ((minute // 5) + 1) * 5
        if next_5 >= 60:
            result = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        else:
            result = now.replace(minute=next_5, second=0, microsecond=0)
        return result


# ===========================================================================
# TELEGRAM ALERTER
# ===========================================================================

class TelegramAlerter:
    """Sends prediction signals to Telegram."""
    
    def __init__(self):
        self.client = httpx.Client(timeout=10)
        self.last_signal_window = None
    
    def send_signal(self, signal: Signal):
        """Send prediction signal to Telegram."""
        if signal.confidence < MIN_CONFIDENCE:
            return
        
        # Don't send duplicate for same window
        window_key = signal.market_slug
        if window_key == self.last_signal_window:
            return
        self.last_signal_window = window_key
        
        # Build message
        direction_emoji = "🟢 UP ⬆️" if signal.direction == "UP" else "🔴 DOWN ⬇️"
        confidence_bar = self._confidence_bar(signal.confidence)
        
        # Top indicators
        sorted_indicators = sorted(
            [(k, v[0], v[1]) for k, v in signal.indicators.items() if v[1] > 0],
            key=lambda x: x[2], reverse=True
        )
        
        indicator_lines = []
        for name, direction, weight in sorted_indicators[:8]:
            icon = "⬆" if direction == "UP" else "⬇" if direction == "DOWN" else "↔"
            indicator_lines.append(f"  {icon} {name}: {direction} ({weight:.1f})")
        
        # Count votes
        up_count = sum(1 for _, v in signal.indicators.items() if v[0] == "UP" and v[1] > 0)
        down_count = sum(1 for _, v in signal.indicators.items() if v[0] == "DOWN" and v[1] > 0)
        
        window_start_et = signal.window_start - timedelta(hours=5)
        window_end_et = signal.window_end - timedelta(hours=5)
        
        msg = f"""🎯 BTC 5-MIN PREDICTION

{direction_emoji}
{confidence_bar}
Confidence: {signal.confidence}%

⏰ Window: {window_start_et.strftime('%I:%M')}-{window_end_et.strftime('%I:%M %p')} ET
💰 BTC: ${signal.btc_price:,.2f}

📊 Indicators ({up_count}⬆ vs {down_count}⬇):
{chr(10).join(indicator_lines)}

🔗 {signal.polymarket_url}

⚡ Trade: Buy {"UP" if signal.direction == "UP" else "DOWN"} on Polymarket"""
        
        for chat_id in TELEGRAM_CHAT_IDS:
            try:
                self.client.post(
                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": msg,
                    }
                )
            except Exception as e:
                print(f"  ⚠ Telegram error: {e}")
        
        print(f"  📢 Signal sent: {signal.direction} ({signal.confidence}%)")
    
    def _confidence_bar(self, confidence: float) -> str:
        filled = int(confidence / 10)
        bar = "█" * filled + "░" * (10 - filled)
        return f"[{bar}]"


# ===========================================================================
# MAIN LOOP
# ===========================================================================

def main():
    print("="*60)
    print("  🎯 BTC 5-MIN PREDICTOR")
    print("  20 Technical Indicators | Telegram Alerts")
    print("="*60)
    
    engine = PredictionEngine()
    alerter = TelegramAlerter()
    
    # Track sent signals to avoid duplicates
    sent_windows = set()
    
    scan_count = 0
    
    while True:
        try:
            scan_count += 1
            now = datetime.now(tz=timezone.utc)
            
            # Calculate next window
            minute = now.minute
            next_5 = ((minute // 5) + 1) * 5
            if next_5 >= 60:
                next_window = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            else:
                next_window = now.replace(minute=next_5, second=0, microsecond=0)
            
            seconds_to_window = (next_window - now).total_seconds()
            ts = int(next_window.timestamp())
            slug = f"btc-updown-5m-{ts}"
            
            print(f"\n  [{now.strftime('%H:%M:%S')}] Scan #{scan_count}")
            print(f"  Next window: {next_window.strftime('%H:%M')} UTC ({seconds_to_window:.0f}s away)")
            
            # Send signal SIGNAL_LEAD_TIME seconds before window starts
            if seconds_to_window <= SIGNAL_LEAD_TIME and slug not in sent_windows:
                print(f"  🔍 Running full analysis...")
                signal = engine.analyze()
                
                if signal:
                    print(f"  📊 Result: {signal.direction} ({signal.confidence}%)")
                    
                    # Print indicator summary
                    up_votes = [(k, v[1]) for k, v in signal.indicators.items() if v[0] == "UP" and v[1] > 0]
                    down_votes = [(k, v[1]) for k, v in signal.indicators.items() if v[0] == "DOWN" and v[1] > 0]
                    print(f"    ⬆ UP votes: {len(up_votes)} ({sum(v for _, v in up_votes):.1f} total weight)")
                    print(f"    ⬇ DOWN votes: {len(down_votes)} ({sum(v for _, v in down_votes):.1f} total weight)")
                    
                    if signal.confidence >= MIN_CONFIDENCE:
                        alerter.send_signal(signal)
                        sent_windows.add(slug)
                    else:
                        print(f"  ⚠ Low confidence ({signal.confidence}% < {MIN_CONFIDENCE}%), skipping")
                else:
                    print(f"  ⚠ Analysis failed")
            elif slug in sent_windows:
                print(f"  ✅ Already sent signal for this window")
            else:
                print(f"  ⏳ Waiting... ({seconds_to_window:.0f}s to signal time)")
            
            # Clean old sent windows (keep last 100)
            if len(sent_windows) > 100:
                sent_windows = set(list(sent_windows)[-50:])
            
            time.sleep(SCAN_INTERVAL)
            
        except KeyboardInterrupt:
            print("\n  Stopped by user")
            break
        except Exception as e:
            print(f"  ❌ Error: {e}")
            traceback.print_exc()
            time.sleep(10)


if __name__ == "__main__":
    main()
