#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║  🎯 BTC 5-MIN DIRECTION PREDICTOR v3                           ║
║  Pure Technical Analysis — NO Polymarket data                   ║
║  Predicts: Will BTC go UP or DOWN in the next 5 minutes?        ║
╚══════════════════════════════════════════════════════════════════╝

HOW IT WORKS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Every 5 minutes Polymarket opens a new "Up or Down" market
• PRICE TO BEAT = BTC price at window start
• If BTC is HIGHER at window end → Up wins
• If BTC is LOWER at window end → Down wins

THIS BOT:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Analyzes BTC on its own (NO Polymarket prices)
• Uses pure technical analysis to predict 5-min direction
• Signals 60s BEFORE each window so you can buy at ~50¢
• Only signals when multiple indicators strongly agree

DATA SOURCES (all from Binance):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• 1-min candles (200) — main analysis timeframe
• 5-min candles (60)  — trend confirmation
• 15-min candles (30) — macro trend
• Order book (50 levels) — buy/sell walls
• Aggregated trades (1000) — who's aggressive buyer/seller
• Funding rate — market sentiment
• Taker buy/sell ratio — aggression direction
"""

import os, sys, json, time, math, traceback
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict

import httpx

# ═══════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════

TELEGRAM_TOKEN = "8331165268:AAEA84wTDNeFuPhRJkjLiUqxxkaPEuL2B-o"
TELEGRAM_CHAT_IDS = ["1688623770", "1675476723"]

BINANCE_SPOT  = "https://api.binance.com/api/v3"
BINANCE_FUTS  = "https://fapi.binance.com"

SCAN_INTERVAL    = 15     # seconds between scans
SIGNAL_LEAD_TIME = 60     # signal this many seconds BEFORE window
MIN_CONFIDENCE   = 70     # skip below this

# ═══════════════════════════════════════════════════════════════
# DATA
# ═══════════════════════════════════════════════════════════════

@dataclass
class Candle:
    ts: float; o: float; h: float; l: float; c: float; v: float

@dataclass
class Prediction:
    direction: str        # UP / DOWN
    confidence: float     # 0-100
    tier: str             # SKIP / WATCH / SIGNAL / SNIPER
    price: float          # BTC price now
    reasons: List[str]
    scores: Dict          # raw indicator scores
    window_start: datetime
    window_end: datetime

# ═══════════════════════════════════════════════════════════════
# BINANCE DATA ENGINE
# ═══════════════════════════════════════════════════════════════

class DataEngine:
    """All data comes from Binance only."""

    def __init__(self):
        self.c = httpx.Client(timeout=10)
        self._cache: Dict[str, Tuple[float, object]] = {}

    # ---------- helpers ----------
    def _get(self, url, params=None, ttl=4):
        key = f"{url}|{json.dumps(params or {}, sort_keys=True)}"
        now = time.time()
        if key in self._cache and now - self._cache[key][0] < ttl:
            return self._cache[key][1]
        try:
            r = self.c.get(url, params=params)
            if r.status_code == 200:
                data = r.json()
                self._cache[key] = (now, data)
                return data
        except Exception as e:
            print(f"    ⚠ API {url.split('/')[-1]}: {e}")
        return self._cache.get(key, (0, None))[1]

    # ---------- candles ----------
    def klines(self, interval="1m", limit=200) -> List[Candle]:
        raw = self._get(f"{BINANCE_SPOT}/klines",
                        {"symbol": "BTCUSDT", "interval": interval, "limit": limit})
        if not raw:
            return []
        return [Candle(k[0]/1000, float(k[1]), float(k[2]),
                       float(k[3]), float(k[4]), float(k[5])) for k in raw]

    # ---------- price ----------
    def price(self) -> float:
        d = self._get(f"{BINANCE_SPOT}/ticker/price", {"symbol": "BTCUSDT"}, ttl=2)
        return float(d["price"]) if d else 0.0

    # ---------- order book ----------
    def orderbook(self, limit=50):
        d = self._get(f"{BINANCE_SPOT}/depth", {"symbol": "BTCUSDT", "limit": limit})
        if not d:
            return [], []
        return d.get("bids", []), d.get("asks", [])

    # ---------- aggregated trades ----------
    def agg_trades(self, limit=1000) -> list:
        return self._get(f"{BINANCE_SPOT}/aggTrades",
                         {"symbol": "BTCUSDT", "limit": limit}) or []

    # ---------- funding rate ----------
    def funding_rate(self) -> Optional[float]:
        d = self._get(f"{BINANCE_FUTS}/fapi/v1/fundingRate",
                      {"symbol": "BTCUSDT", "limit": 1}, ttl=30)
        if d and len(d):
            return float(d[-1]["fundingRate"])
        return None

    # ---------- taker buy/sell ----------
    def taker_ratio(self) -> Optional[float]:
        d = self._get(f"{BINANCE_FUTS}/futures/data/takerlongshortRatio",
                      {"symbol": "BTCUSDT", "period": "5m", "limit": 1}, ttl=15)
        if d and len(d):
            bv = float(d[-1].get("buyVol", 0))
            sv = float(d[-1].get("sellVol", 0))
            total = bv + sv
            return (bv - sv) / total if total else 0.0
        return None

    # ---------- long/short ratio ----------
    def long_short(self) -> Optional[float]:
        d = self._get(f"{BINANCE_FUTS}/futures/data/topLongShortAccountRatio",
                      {"symbol": "BTCUSDT", "period": "5m", "limit": 1}, ttl=15)
        if d and len(d):
            return float(d[-1]["longShortRatio"])
        return None


# ═══════════════════════════════════════════════════════════════
# INDICATOR LIBRARY
# ═══════════════════════════════════════════════════════════════

def _ema(data, p):
    if not data: return []
    m = 2/(p+1); r = [data[0]]
    for v in data[1:]: r.append((v-r[-1])*m + r[-1])
    return r

def _rsi(closes, p=14):
    if len(closes) < p+1: return 50.0
    d = [closes[i]-closes[i-1] for i in range(1, len(closes))]
    g = [max(x,0) for x in d]; l = [max(-x,0) for x in d]
    ag = sum(g[-p:])/p; al = sum(l[-p:])/p
    if al == 0: return 100.0
    return 100 - 100/(1 + ag/al)

def _macd(closes):
    if len(closes) < 26: return 0,0,0
    e12 = _ema(closes,12); e26 = _ema(closes,26)
    ml = [e12[i]-e26[i] for i in range(len(closes))]
    sl = _ema(ml, 9)
    return ml[-1], sl[-1], ml[-1]-sl[-1]

def _bb_pos(closes, p=20):
    if len(closes)<p: return 0.5
    w = closes[-p:]; m = sum(w)/p
    s = math.sqrt(sum((x-m)**2 for x in w)/p) or 1
    u = m+2*s; lo = m-2*s
    return (closes[-1]-lo)/(u-lo) if u!=lo else 0.5

def _stoch_rsi(closes, p=14):
    if len(closes)<p*2: return 50
    rsis = [_rsi(closes[:i], p) for i in range(p, len(closes)+1)]
    if len(rsis)<p: return 50
    r = rsis[-p:]; mn,mx = min(r),max(r)
    return (rsis[-1]-mn)/(mx-mn)*100 if mx!=mn else 50

def _atr(candles, p=14):
    if len(candles)<p+1: return 0
    trs = [max(candles[i].h-candles[i].l,
               abs(candles[i].h-candles[i-1].c),
               abs(candles[i].l-candles[i-1].c)) for i in range(1,len(candles))]
    return sum(trs[-p:])/p

def _adx(candles, p=14):
    if len(candles)<p*2: return 25, 0, 0
    pdm,mdm,trs = [],[],[]
    for i in range(1,len(candles)):
        up = candles[i].h-candles[i-1].h
        dn = candles[i-1].l-candles[i].l
        pdm.append(up if up>dn and up>0 else 0)
        mdm.append(dn if dn>up and dn>0 else 0)
        trs.append(max(candles[i].h-candles[i].l,
                       abs(candles[i].h-candles[i-1].c),
                       abs(candles[i].l-candles[i-1].c)))
    at = sum(trs[-p:])/p
    if at==0: return 0,0,0
    ap = sum(pdm[-p:])/p; am = sum(mdm[-p:])/p
    pdi = ap/at*100; mdi = am/at*100
    dx = abs(pdi-mdi)/(pdi+mdi)*100 if pdi+mdi else 0
    return dx, pdi, mdi

def _vwap(candles, p=30):
    r = candles[-p:]
    tv = sum(c.v for c in r)
    if tv==0: return r[-1].c
    return sum(((c.h+c.l+c.c)/3)*c.v for c in r)/tv

def _williams(candles, p=14):
    if len(candles)<p: return -50
    r = candles[-p:]
    hi = max(c.h for c in r); lo = min(c.l for c in r)
    return (hi-candles[-1].c)/(hi-lo)*-100 if hi!=lo else -50

def _cci(candles, p=20):
    if len(candles)<p: return 0
    r = candles[-p:]
    tp = [(c.h+c.l+c.c)/3 for c in r]; m = sum(tp)/p
    md = sum(abs(t-m) for t in tp)/p
    return (tp[-1]-m)/(0.015*md) if md else 0

def _obv_slope(candles, short=5, long_=20):
    obv = [0.0]
    for i in range(1,len(candles)):
        if candles[i].c>candles[i-1].c: obv.append(obv[-1]+candles[i].v)
        elif candles[i].c<candles[i-1].c: obv.append(obv[-1]-candles[i].v)
        else: obv.append(obv[-1])
    if len(obv)<long_: return 0
    sa = sum(obv[-short:])/short
    la = sum(obv[-long_:])/long_
    return 1 if sa>la else (-1 if sa<la else 0)


# ═══════════════════════════════════════════════════════════════
# PREDICTION ENGINE
# ═══════════════════════════════════════════════════════════════

class PredictionEngine:
    """
    Pure BTC technical analysis.
    Outputs a weighted score:
      > 0 = UP prediction
      < 0 = DOWN prediction
      magnitude = confidence

    INDICATOR GROUPS (each scored -10 to +10):
    ─────────────────────────────────────────
    A. Trend      : EMA cross, EMA50, ADX direction
    B. Momentum   : RSI, MACD hist, recent candle direction
    C. Mean-Rev   : Bollinger, StochRSI, Williams%R, CCI
    D. Volume     : OBV slope, volume spike, buy/sell ratio
    E. Order Flow : book imbalance, trade aggression
    F. Multi-TF   : 5m + 15m trend agreement
    G. Futures    : funding rate, taker ratio, L/S ratio
    """

    def __init__(self):
        self.data = DataEngine()

    def predict(self) -> Optional[Prediction]:
        c1  = self.data.klines("1m", 200)
        c5  = self.data.klines("5m", 60)
        c15 = self.data.klines("15m", 30)
        if len(c1) < 50:
            return None

        price = c1[-1].c
        cl1  = [c.c for c in c1]
        cl5  = [c.c for c in c5]  if c5  else cl1
        cl15 = [c.c for c in c15] if c15 else cl1

        scores: Dict[str, float] = {}   # each -10..+10
        reasons: List[str] = []

        # ─────────────────────────────────────
        # A. TREND (weight = high)
        # ─────────────────────────────────────
        e9  = _ema(cl1, 9)
        e21 = _ema(cl1, 21)
        e50 = _ema(cl1, 50)

        ema_gap_bps = (e9[-1] - e21[-1]) / price * 10000
        trend_score = 0.0

        # EMA 9/21 cross direction
        if ema_gap_bps > 3:
            trend_score += 4
            reasons.append(f"EMA9>21 (+{ema_gap_bps:.1f}bps)")
        elif ema_gap_bps < -3:
            trend_score -= 4
            reasons.append(f"EMA9<21 ({ema_gap_bps:.1f}bps)")
        else:
            reasons.append("EMA9≈21 (flat)")

        # Fresh cross? (huge signal)
        if len(e9)>2 and len(e21)>2:
            prev_gap = e9[-2] - e21[-2]
            curr_gap = e9[-1] - e21[-1]
            if prev_gap <= 0 < curr_gap:
                trend_score += 3
                reasons.append("🔥 Fresh bullish EMA cross!")
            elif prev_gap >= 0 > curr_gap:
                trend_score -= 3
                reasons.append("🔥 Fresh bearish EMA cross!")

        # Price vs EMA50
        if price > e50[-1] * 1.0005:
            trend_score += 2
        elif price < e50[-1] * 0.9995:
            trend_score -= 2

        # ADX — trend strength
        adx_val, pdi, mdi = _adx(c1)
        if adx_val > 25:
            # Strong trend — amplify direction
            if pdi > mdi:
                trend_score += 2
                reasons.append(f"ADX {adx_val:.0f} (strong ↑ trend)")
            else:
                trend_score -= 2
                reasons.append(f"ADX {adx_val:.0f} (strong ↓ trend)")

        scores["trend"] = max(-10, min(10, trend_score))

        # ─────────────────────────────────────
        # B. MOMENTUM
        # ─────────────────────────────────────
        mom_score = 0.0

        # RSI(14)
        rsi14 = _rsi(cl1, 14)
        rsi7  = _rsi(cl1, 7)
        if rsi14 > 65: mom_score += 2; reasons.append(f"RSI14 bullish ({rsi14:.0f})")
        elif rsi14 < 35: mom_score -= 2; reasons.append(f"RSI14 bearish ({rsi14:.0f})")

        # RSI(7) — fast
        if rsi7 > 75: mom_score += 2
        elif rsi7 < 25: mom_score -= 2

        # MACD histogram
        _, _, hist = _macd(cl1)
        if hist > 0:
            mom_score += 2
            if len(cl1) > 27:
                _, _, prev_hist = _macd(cl1[:-1])
                if hist > prev_hist:
                    mom_score += 1
                    reasons.append("MACD accelerating ↑")
                else:
                    reasons.append("MACD ↑ but slowing")
        else:
            mom_score -= 2
            if len(cl1) > 27:
                _, _, prev_hist = _macd(cl1[:-1])
                if hist < prev_hist:
                    mom_score -= 1
                    reasons.append("MACD accelerating ↓")
                else:
                    reasons.append("MACD ↓ but slowing")

        # Last 5 candles direction
        greens = sum(1 for c in c1[-5:] if c.c > c.o)
        if greens >= 4:
            mom_score += 2
            reasons.append(f"{greens}/5 green candles")
        elif greens <= 1:
            mom_score -= 2
            reasons.append(f"{5-greens}/5 red candles")

        # Price change last 3 minutes
        if len(cl1) >= 4:
            chg3 = (cl1[-1] - cl1[-4]) / cl1[-4] * 10000  # bps
            if chg3 > 5:
                mom_score += 2
                reasons.append(f"Last 3m: +{chg3:.0f}bps ↑")
            elif chg3 < -5:
                mom_score -= 2
                reasons.append(f"Last 3m: {chg3:.0f}bps ↓")

        scores["momentum"] = max(-10, min(10, mom_score))

        # ─────────────────────────────────────
        # C. MEAN REVERSION
        # ─────────────────────────────────────
        mr_score = 0.0

        # Bollinger position
        bb = _bb_pos(cl1)
        if bb > 0.90:
            mr_score -= 3  # overbought → may revert down
            reasons.append(f"Bollinger top ({bb:.0%}) ⚠")
        elif bb < 0.10:
            mr_score += 3  # oversold → may revert up
            reasons.append(f"Bollinger bottom ({bb:.0%}) ⚠")
        elif bb > 0.70:
            mr_score -= 1
        elif bb < 0.30:
            mr_score += 1

        # StochRSI
        stoch = _stoch_rsi(cl1)
        if stoch > 85: mr_score -= 2
        elif stoch < 15: mr_score += 2

        # Williams %R
        wr = _williams(c1)
        if wr > -10: mr_score -= 2; reasons.append(f"Williams peaked ({wr:.0f})")
        elif wr < -90: mr_score += 2; reasons.append(f"Williams bottomed ({wr:.0f})")

        # CCI
        cci = _cci(c1)
        if cci > 150: mr_score -= 2; reasons.append(f"CCI extreme ({cci:.0f})")
        elif cci < -150: mr_score += 2; reasons.append(f"CCI extreme ({cci:.0f})")

        scores["mean_rev"] = max(-10, min(10, mr_score))

        # ─────────────────────────────────────
        # D. VOLUME
        # ─────────────────────────────────────
        vol_score = 0.0

        # OBV slope
        obv_dir = _obv_slope(c1)
        if obv_dir > 0:
            vol_score += 2
            reasons.append("OBV ↑ (volume confirms)")
        elif obv_dir < 0:
            vol_score -= 2
            reasons.append("OBV ↓ (volume confirms)")

        # Volume spike on last candle
        if len(c1) > 20:
            avg_v = sum(c.v for c in c1[-21:-1])/20
            cur_v = c1[-1].v
            vr = cur_v / avg_v if avg_v else 1
            if vr > 2.5:
                d = 1 if c1[-1].c > c1[-1].o else -1
                vol_score += 3 * d
                reasons.append(f"🔥 Volume spike {vr:.1f}x ({'↑' if d>0 else '↓'})")
            elif vr > 1.5:
                d = 1 if c1[-1].c > c1[-1].o else -1
                vol_score += 1 * d

        # VWAP distance
        vwap = _vwap(c1, 30)
        vwap_dist_bps = (price - vwap) / price * 10000
        if vwap_dist_bps > 5:
            vol_score += 1  # above VWAP → bullish
        elif vwap_dist_bps < -5:
            vol_score -= 1

        scores["volume"] = max(-10, min(10, vol_score))

        # ─────────────────────────────────────
        # E. ORDER FLOW
        # ─────────────────────────────────────
        of_score = 0.0

        # Book imbalance
        bids, asks = self.data.orderbook(50)
        if bids and asks:
            bv = sum(float(b[1]) for b in bids)
            av = sum(float(a[1]) for a in asks)
            tot = bv + av
            if tot > 0:
                imb = (bv - av) / tot
                if imb > 0.20:
                    of_score += 3
                    reasons.append(f"Book heavy bids ({imb:.0%})")
                elif imb < -0.20:
                    of_score -= 3
                    reasons.append(f"Book heavy asks ({abs(imb):.0%})")
                elif imb > 0.08:
                    of_score += 1
                elif imb < -0.08:
                    of_score -= 1

        # Trade flow (aggressive buyers vs sellers)
        trades = self.data.agg_trades(800)
        if trades:
            buy_q = sum(float(t["q"]) for t in trades if not t.get("m"))
            sell_q = sum(float(t["q"]) for t in trades if t.get("m"))
            total_q = buy_q + sell_q
            if total_q > 0:
                tf = (buy_q - sell_q) / total_q
                if tf > 0.15:
                    of_score += 3
                    reasons.append(f"🔥 Aggressive buyers ({tf:.0%})")
                elif tf < -0.15:
                    of_score -= 3
                    reasons.append(f"🔥 Aggressive sellers ({abs(tf):.0%})")
                elif tf > 0.05:
                    of_score += 1
                elif tf < -0.05:
                    of_score -= 1

        scores["order_flow"] = max(-10, min(10, of_score))

        # ─────────────────────────────────────
        # F. MULTI-TIMEFRAME
        # ─────────────────────────────────────
        mtf_score = 0.0

        # 5m trend
        if len(cl5) > 21:
            e9_5 = _ema(cl5, 9); e21_5 = _ema(cl5, 21)
            if e9_5[-1] > e21_5[-1]:
                mtf_score += 2
            else:
                mtf_score -= 2
            r5 = _rsi(cl5, 14)
            if r5 > 60: mtf_score += 1
            elif r5 < 40: mtf_score -= 1

        # 15m trend
        if len(cl15) > 21:
            e9_15 = _ema(cl15, 9); e21_15 = _ema(cl15, 21)
            if e9_15[-1] > e21_15[-1]:
                mtf_score += 2
            else:
                mtf_score -= 2
            r15 = _rsi(cl15, 14)
            if r15 > 60: mtf_score += 1
            elif r15 < 40: mtf_score -= 1

        if mtf_score >= 4:
            reasons.append(f"🔥 Multi-TF aligned UP")
        elif mtf_score <= -4:
            reasons.append(f"🔥 Multi-TF aligned DOWN")

        scores["multi_tf"] = max(-10, min(10, mtf_score))

        # ─────────────────────────────────────
        # G. FUTURES SENTIMENT
        # ─────────────────────────────────────
        fut_score = 0.0

        # Funding rate
        fr = self.data.funding_rate()
        if fr is not None:
            if fr > 0.0005:
                fut_score -= 1  # high funding → contrarian short
            elif fr < -0.0005:
                fut_score += 1  # negative funding → contrarian long

        # Taker ratio
        tr = self.data.taker_ratio()
        if tr is not None:
            if tr > 0.1:
                fut_score += 2
                reasons.append(f"Takers buying ({tr:.0%})")
            elif tr < -0.1:
                fut_score -= 2
                reasons.append(f"Takers selling ({abs(tr):.0%})")

        # Long/short ratio
        ls = self.data.long_short()
        if ls is not None:
            if ls > 1.8:
                fut_score -= 1  # crowded long → contrarian
            elif ls < 0.6:
                fut_score += 1  # crowded short → contrarian

        scores["futures"] = max(-10, min(10, fut_score))

        # ═══════════════════════════════════════════════
        # WEIGHTED COMBINATION
        # ═══════════════════════════════════════════════
        weights = {
            "trend":      3.0,   # trend is king for continuation
            "momentum":   3.0,   # short-term momentum matters
            "mean_rev":   1.5,   # mean reversion is counter-trend
            "volume":     2.0,   # volume confirms moves
            "order_flow": 2.5,   # real-time order flow is powerful
            "multi_tf":   2.0,   # multi-timeframe alignment
            "futures":    1.0,   # futures data is supplementary
        }

        raw = sum(scores[k] * weights[k] for k in scores)
        max_possible = sum(10 * w for w in weights.values())  # 150

        # Convert to 50-100 scale
        # raw ranges from -max_possible to +max_possible
        # We want: 0 raw → 50%, max_possible → 100%
        abs_raw = abs(raw)
        confidence = 50 + (abs_raw / max_possible) * 50

        direction = "UP" if raw > 0 else "DOWN"

        # ─── Adjustments ───

        # CONFLICT PENALTY: if trend and mean_rev disagree strongly,
        # reduce confidence (market is confused)
        if scores["trend"] * scores["mean_rev"] < -15:
            confidence *= 0.88
            reasons.append("⚠ Trend vs mean-reversion conflict")

        # MOMENTUM + ORDER FLOW agreement bonus
        if scores["momentum"] * scores["order_flow"] > 10:
            confidence = min(98, confidence * 1.05)
            reasons.append("✅ Momentum + order flow aligned")

        # LOW ADX penalty (no clear trend)
        if adx_val < 15:
            confidence *= 0.93
            reasons.append(f"⚠ Low ADX ({adx_val:.0f}) — no trend")

        # ATR check — high volatility adds uncertainty
        atr = _atr(c1)
        atr_pct = atr / price * 100
        if atr_pct > 0.15:
            confidence *= 0.95

        confidence = max(30, min(98, confidence))

        # Tier
        if confidence >= 90: tier = "SNIPER"
        elif confidence >= 80: tier = "SIGNAL"
        elif confidence >= 70: tier = "WATCH"
        else: tier = "SKIP"

        # Add breakdown
        reasons.append(f"[Trend:{scores['trend']:+.0f} Mom:{scores['momentum']:+.0f} "
                       f"MR:{scores['mean_rev']:+.0f} Vol:{scores['volume']:+.0f} "
                       f"OF:{scores['order_flow']:+.0f} MTF:{scores['multi_tf']:+.0f} "
                       f"Fut:{scores['futures']:+.0f}]")
        reasons.append(f"Raw={raw:+.1f}/{max_possible:.0f}")

        # Calculate next window
        now = datetime.now(tz=timezone.utc)
        m = now.minute
        next5 = ((m//5)+1)*5
        if next5 >= 60:
            ws = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        else:
            ws = now.replace(minute=next5, second=0, microsecond=0)

        return Prediction(
            direction=direction,
            confidence=round(confidence, 1),
            tier=tier,
            price=price,
            reasons=reasons,
            scores=scores,
            window_start=ws,
            window_end=ws + timedelta(minutes=5),
        )


# ═══════════════════════════════════════════════════════════════
# TELEGRAM
# ═══════════════════════════════════════════════════════════════

class Telegram:
    def __init__(self):
        self.c = httpx.Client(timeout=10)
        self.sent: set = set()

    def send(self, p: Prediction):
        key = p.window_start.isoformat()
        if key in self.sent or p.confidence < MIN_CONFIDENCE:
            return
        self.sent.add(key)

        tier_label = {"SNIPER":"🎯🔥 SNIPER","SIGNAL":"🟢 STRONG",
                      "WATCH":"🟡 WATCH"}.get(p.tier, p.tier)
        d = "⬆️ UP" if p.direction=="UP" else "⬇️ DOWN"
        bar = "█"*int(p.confidence/10) + "░"*(10-int(p.confidence/10))

        ws_et = p.window_start - timedelta(hours=5)
        we_et = p.window_end   - timedelta(hours=5)

        rl = "\n".join(f"  • {r}" for r in p.reasons if not r.startswith("[") and not r.startswith("Raw"))

        slug = f"btc-updown-5m-{int(p.window_start.timestamp())}"

        msg = f"""{tier_label}

{d}  |  Confidence: {p.confidence}%
[{bar}]

⏰ {ws_et.strftime('%I:%M')}-{we_et.strftime('%I:%M %p')} ET
💰 BTC: ${p.price:,.2f}

📋 Why:
{rl}

🔗 https://polymarket.com/event/{slug}

⚡ Buy {p.direction} NOW"""

        for cid in TELEGRAM_CHAT_IDS:
            try:
                self.c.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                            json={"chat_id": cid, "text": msg})
            except Exception as e:
                print(f"    ⚠ TG: {e}")

        print(f"    📢 [{p.tier}] {p.direction} {p.confidence}% → Telegram ✅")

    def cleanup(self):
        if len(self.sent) > 300:
            self.sent = set(list(self.sent)[-50:])


# ═══════════════════════════════════════════════════════════════
# MAIN LOOP
# ═══════════════════════════════════════════════════════════════

def main():
    print("="*60)
    print("  🎯 BTC 5-MIN DIRECTION PREDICTOR v3")
    print("  Pure Technical Analysis — Predicts BTC direction")
    print("  Signals 60s before each 5-min window")
    print(f"  Min confidence: {MIN_CONFIDENCE}%")
    print("="*60)

    engine = PredictionEngine()
    tg     = Telegram()
    scan   = 0
    stats  = {"sent": 0, "skip": 0}

    while True:
        try:
            scan += 1
            now = datetime.now(tz=timezone.utc)

            # Next 5-min window
            m = now.minute
            next5 = ((m//5)+1)*5
            if next5 >= 60:
                nw = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            else:
                nw = now.replace(minute=next5, second=0, microsecond=0)

            secs_to = (nw - now).total_seconds()
            slug = f"btc-updown-5m-{int(nw.timestamp())}"

            print(f"\n  [{now.strftime('%H:%M:%S')}] Scan #{scan} | "
                  f"Next window {nw.strftime('%H:%M')} in {secs_to:.0f}s")

            # Only analyze when close to window start
            if secs_to > SIGNAL_LEAD_TIME:
                wait = min(secs_to - SIGNAL_LEAD_TIME, SCAN_INTERVAL)
                print(f"    ⏳ Waiting {wait:.0f}s...")
                time.sleep(wait)
                continue

            # Already sent?
            if nw.isoformat() in tg.sent:
                print(f"    ✅ Already handled")
                time.sleep(max(secs_to + 5, SCAN_INTERVAL))
                continue

            # ── ANALYZE ──
            print(f"    🔍 Full analysis...")
            pred = engine.predict()

            if not pred:
                print(f"    ⚠ No data")
                time.sleep(SCAN_INTERVAL)
                continue

            print(f"    📊 {pred.direction} | {pred.confidence}% | {pred.tier}")
            for r in pred.reasons[:6]:
                print(f"       {r}")

            if pred.tier != "SKIP":
                tg.send(pred)
                stats["sent"] += 1
            else:
                stats["skip"] += 1
                print(f"    ⏭ SKIP ({pred.confidence}% < {MIN_CONFIDENCE}%)")

            total = stats["sent"] + stats["skip"]
            print(f"    📈 {stats['sent']}/{total} signaled ({stats['sent']/total*100:.0f}%)")

            tg.cleanup()
            # Wait for next window
            time.sleep(max(secs_to + 5, SCAN_INTERVAL))

        except KeyboardInterrupt:
            print("\n  Stopped.")
            break
        except Exception as e:
            print(f"    ❌ {e}")
            traceback.print_exc()
            time.sleep(10)


if __name__ == "__main__":
    main()
