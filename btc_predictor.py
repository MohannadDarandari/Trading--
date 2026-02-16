#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║  🎯 BTC 5-MIN PREDICTOR v4 — ALWAYS SIGNALS                   ║
║  Every 5 minutes = 1 prediction. No skipping.                   ║
║  Deep sources: Binance spot+futures, liquidations,              ║
║  whale trades, funding, open interest, CVD, order flow          ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os, sys, json, time, math, traceback
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict
import httpx

# ═══════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════

TELEGRAM_TOKEN = "8331165268:AAEA84wTDNeFuPhRJkjLiUqxxkaPEuL2B-o"
TELEGRAM_CHAT_IDS = ["1688623770", "1675476723"]

BINANCE      = "https://api.binance.com/api/v3"
BINANCE_FUTS = "https://fapi.binance.com"

# Signal 60 seconds BEFORE each 5-min window
LEAD_TIME = 60

# ═══════════════════════════════════════════════════════
# DATA
# ═══════════════════════════════════════════════════════

@dataclass
class Candle:
    ts: float; o: float; h: float; l: float; c: float; v: float

@dataclass
class Prediction:
    direction: str       # UP / DOWN
    confidence: float    # 50-99
    price: float
    reasons: List[str]
    scores: Dict
    window_start: datetime
    window_end: datetime

# ═══════════════════════════════════════════════════════
# DEEP DATA ENGINE — all the "under the table" sources
# ═══════════════════════════════════════════════════════

class DeepData:
    def __init__(self):
        self.c = httpx.Client(timeout=8)
        self._cache: Dict[str, Tuple[float, object]] = {}

    def _get(self, url, params=None, ttl=4):
        key = f"{url}|{json.dumps(params or {}, sort_keys=True)}"
        now = time.time()
        if key in self._cache and now - self._cache[key][0] < ttl:
            return self._cache[key][1]
        try:
            r = self.c.get(url, params=params)
            if r.status_code == 200:
                d = r.json()
                self._cache[key] = (now, d)
                return d
        except:
            pass
        cached = self._cache.get(key)
        return cached[1] if cached else None

    # ── Spot ──
    def klines(self, tf="1m", n=200):
        raw = self._get(f"{BINANCE}/klines", {"symbol":"BTCUSDT","interval":tf,"limit":n})
        return [Candle(k[0]/1000,float(k[1]),float(k[2]),float(k[3]),float(k[4]),float(k[5])) for k in (raw or [])]

    def price(self):
        d = self._get(f"{BINANCE}/ticker/price", {"symbol":"BTCUSDT"}, 2)
        return float(d["price"]) if d else 0

    def book(self, n=100):
        d = self._get(f"{BINANCE}/depth", {"symbol":"BTCUSDT","limit":n})
        return (d.get("bids",[]), d.get("asks",[])) if d else ([],[])

    def agg_trades(self, n=1000):
        return self._get(f"{BINANCE}/aggTrades", {"symbol":"BTCUSDT","limit":n}) or []

    # ── Futures — the REAL hidden data ──
    def funding(self):
        d = self._get(f"{BINANCE_FUTS}/fapi/v1/fundingRate", {"symbol":"BTCUSDT","limit":1}, 30)
        return float(d[-1]["fundingRate"]) if d else None

    def open_interest(self):
        d = self._get(f"{BINANCE_FUTS}/fapi/v1/openInterest", {"symbol":"BTCUSDT"}, 10)
        return float(d["openInterest"]) if d else None

    def oi_history(self):
        """OI change over last periods — shows positioning shifts."""
        d = self._get(f"{BINANCE_FUTS}/futures/data/openInterestHist",
                      {"symbol":"BTCUSDT","period":"5m","limit":12}, 15)
        return d or []

    def long_short_ratio(self):
        d = self._get(f"{BINANCE_FUTS}/futures/data/topLongShortAccountRatio",
                      {"symbol":"BTCUSDT","period":"5m","limit":6}, 10)
        return d or []

    def taker_buy_sell(self):
        d = self._get(f"{BINANCE_FUTS}/futures/data/takerlongshortRatio",
                      {"symbol":"BTCUSDT","period":"5m","limit":6}, 10)
        return d or []

    def liquidations_proxy(self):
        """Use futures klines volume spike as liquidation proxy."""
        d = self._get(f"{BINANCE_FUTS}/fapi/v1/klines",
                      {"symbol":"BTCUSDT","interval":"1m","limit":10}, 5)
        if not d: return 0, 0
        # Taker buy base asset volume is index 9
        recent_vols = [float(k[5]) for k in d]  # quote volume
        taker_buys  = [float(k[9]) for k in d]  # taker buy volume
        avg = sum(recent_vols)/len(recent_vols) if recent_vols else 1
        last = recent_vols[-1] if recent_vols else 0
        taker_buy_pct = sum(taker_buys)/sum(recent_vols) if sum(recent_vols) else 0.5
        return last/avg if avg else 1, taker_buy_pct

    def futures_klines(self, tf="1m", n=60):
        raw = self._get(f"{BINANCE_FUTS}/fapi/v1/klines",
                        {"symbol":"BTCUSDT","interval":tf,"limit":n}, 5)
        return [Candle(k[0]/1000,float(k[1]),float(k[2]),float(k[3]),float(k[4]),float(k[5])) for k in (raw or [])]

    def spot_futures_spread(self):
        """Premium of futures over spot — tells you leverage direction."""
        spot = self.price()
        futs = self._get(f"{BINANCE_FUTS}/fapi/v1/ticker/price", {"symbol":"BTCUSDT"}, 3)
        if futs and spot:
            fp = float(futs["price"])
            return (fp - spot) / spot * 10000  # basis in bps
        return 0


# ═══════════════════════════════════════════════════════
# INDICATORS
# ═══════════════════════════════════════════════════════

def _ema(d, p):
    if not d: return []
    m=2/(p+1); r=[d[0]]
    for v in d[1:]: r.append((v-r[-1])*m+r[-1])
    return r

def _rsi(c, p=14):
    if len(c)<p+1: return 50
    d=[c[i]-c[i-1] for i in range(1,len(c))]
    g=[max(x,0) for x in d]; l=[max(-x,0) for x in d]
    ag=sum(g[-p:])/p; al=sum(l[-p:])/p
    return 100-100/(1+ag/al) if al else 100

def _macd_hist(c):
    if len(c)<26: return 0
    e12=_ema(c,12); e26=_ema(c,26)
    ml=[e12[i]-e26[i] for i in range(len(c))]
    sl=_ema(ml,9)
    return ml[-1]-sl[-1]

def _bb_pos(c, p=20):
    if len(c)<p: return 0.5
    w=c[-p:]; m=sum(w)/p
    s=math.sqrt(sum((x-m)**2 for x in w)/p) or 1
    return (c[-1]-(m-2*s))/((m+2*s)-(m-2*s)) if (m+2*s)!=(m-2*s) else 0.5

def _stoch_rsi(c, p=14):
    if len(c)<p*2: return 50
    rs=[_rsi(c[:i],p) for i in range(p,len(c)+1)]
    if len(rs)<p: return 50
    r=rs[-p:]; mn,mx=min(r),max(r)
    return (rs[-1]-mn)/(mx-mn)*100 if mx!=mn else 50

def _atr(candles, p=14):
    if len(candles)<p+1: return 0
    trs=[max(candles[i].h-candles[i].l, abs(candles[i].h-candles[i-1].c),
             abs(candles[i].l-candles[i-1].c)) for i in range(1,len(candles))]
    return sum(trs[-p:])/p

def _adx_dir(candles, p=14):
    """Returns (adx, +DI > -DI)."""
    if len(candles)<p*2: return 25, True
    pdm,mdm,trs=[],[],[]
    for i in range(1,len(candles)):
        up=candles[i].h-candles[i-1].h; dn=candles[i-1].l-candles[i].l
        pdm.append(up if up>dn and up>0 else 0)
        mdm.append(dn if dn>up and dn>0 else 0)
        trs.append(max(candles[i].h-candles[i].l, abs(candles[i].h-candles[i-1].c),
                       abs(candles[i].l-candles[i-1].c)))
    at=sum(trs[-p:])/p
    if at==0: return 0, True
    ap=sum(pdm[-p:])/p; am=sum(mdm[-p:])/p
    pdi=ap/at*100; mdi=am/at*100
    dx=abs(pdi-mdi)/(pdi+mdi)*100 if pdi+mdi else 0
    return dx, pdi>mdi

def _obv_dir(candles, s=5, l=20):
    obv=[0.0]
    for i in range(1,len(candles)):
        if candles[i].c>candles[i-1].c: obv.append(obv[-1]+candles[i].v)
        elif candles[i].c<candles[i-1].c: obv.append(obv[-1]-candles[i].v)
        else: obv.append(obv[-1])
    if len(obv)<l: return 0
    return 1 if sum(obv[-s:])/s > sum(obv[-l:])/l else -1

def _cvd(trades):
    """Cumulative Volume Delta from trades. Positive = buyers aggressive."""
    if not trades: return 0
    delta = 0
    for t in trades:
        q = float(t.get("q", 0))
        if t.get("m"):  # maker is buyer → taker SOLD
            delta -= q
        else:  # taker bought
            delta += q
    return delta


# ═══════════════════════════════════════════════════════
# 🧠 THE BRAIN — predicts every 5 minutes, NO SKIP
# ═══════════════════════════════════════════════════════

class Brain:
    def __init__(self):
        self.data = DeepData()

    def predict(self) -> Prediction:
        # ── Fetch everything in parallel-ish ──
        c1   = self.data.klines("1m", 200)
        c5   = self.data.klines("5m", 60)
        c15  = self.data.klines("15m", 30)
        fc1  = self.data.futures_klines("1m", 30)  # futures candles

        price = self.data.price() or (c1[-1].c if c1 else 0)
        cl1  = [c.c for c in c1]
        cl5  = [c.c for c in c5] if c5 else cl1
        cl15 = [c.c for c in c15] if c15 else cl1

        S = {}   # scores by group
        R = []   # reasons

        # ═══════════════════════════════════════
        # 1. TREND (weight 3)
        # ═══════════════════════════════════════
        s = 0
        if len(cl1) > 21:
            e9 = _ema(cl1,9); e21 = _ema(cl1,21); e50 = _ema(cl1,50)
            gap = (e9[-1]-e21[-1])/price*10000
            if gap > 3: s += 4; R.append(f"EMA9>21 +{gap:.0f}bps")
            elif gap < -3: s -= 4; R.append(f"EMA9<21 {gap:.0f}bps")
            # Fresh cross
            if len(e9)>2:
                pg = e9[-2]-e21[-2]; cg = e9[-1]-e21[-1]
                if pg<=0<cg: s += 3; R.append("🔥 Bullish EMA cross!")
                elif pg>=0>cg: s -= 3; R.append("🔥 Bearish EMA cross!")
            if price > e50[-1]: s += 1
            else: s -= 1
            adx, up = _adx_dir(c1)
            if adx > 25:
                s += 2 if up else -2
                R.append(f"ADX {adx:.0f} ({'↑' if up else '↓'})")
        S["trend"] = max(-10,min(10,s))

        # ═══════════════════════════════════════
        # 2. MOMENTUM (weight 3)
        # ═══════════════════════════════════════
        s = 0
        rsi14 = _rsi(cl1, 14)
        rsi7  = _rsi(cl1, 7)
        if rsi14 > 60: s += 2
        elif rsi14 < 40: s -= 2
        if rsi7 > 70: s += 2
        elif rsi7 < 30: s -= 2
        R.append(f"RSI14={rsi14:.0f} RSI7={rsi7:.0f}")

        h = _macd_hist(cl1)
        if h > 0: s += 2
        else: s -= 2
        if len(cl1)>27:
            ph = _macd_hist(cl1[:-1])
            if h > 0 and h > ph: s += 1; R.append("MACD accel ↑")
            elif h < 0 and h < ph: s -= 1; R.append("MACD accel ↓")

        # Last 5 candles
        if len(c1) >= 5:
            gr = sum(1 for c in c1[-5:] if c.c > c.o)
            if gr >= 4: s += 2; R.append(f"{gr}/5 green")
            elif gr <= 1: s -= 2; R.append(f"{5-gr}/5 red")

        # Recent price change (3m)
        if len(cl1) >= 4:
            ch = (cl1[-1]-cl1[-4])/cl1[-4]*10000
            if ch > 5: s += 2; R.append(f"3m: +{ch:.0f}bps")
            elif ch < -5: s -= 2; R.append(f"3m: {ch:.0f}bps")
        S["momentum"] = max(-10,min(10,s))

        # ═══════════════════════════════════════
        # 3. MEAN REVERSION (weight 1.5)
        # ═══════════════════════════════════════
        s = 0
        bb = _bb_pos(cl1)
        if bb > 0.90: s -= 3; R.append(f"BB top {bb:.0%}")
        elif bb < 0.10: s += 3; R.append(f"BB bottom {bb:.0%}")
        elif bb > 0.75: s -= 1
        elif bb < 0.25: s += 1

        sr = _stoch_rsi(cl1)
        if sr > 85: s -= 2
        elif sr < 15: s += 2
        S["mean_rev"] = max(-10,min(10,s))

        # ═══════════════════════════════════════
        # 4. ORDER FLOW — the money signal (weight 3)
        # ═══════════════════════════════════════
        s = 0

        # Book imbalance
        bids, asks = self.data.book(100)
        if bids and asks:
            bv = sum(float(b[1]) for b in bids)
            av = sum(float(a[1]) for a in asks)
            tot = bv+av
            if tot:
                imb = (bv-av)/tot
                if imb > 0.25: s += 3; R.append(f"📕 Book bids {imb:.0%}")
                elif imb < -0.25: s -= 3; R.append(f"📕 Book asks {abs(imb):.0%}")
                elif imb > 0.10: s += 1
                elif imb < -0.10: s -= 1

        # CVD — Cumulative Volume Delta
        trades = self.data.agg_trades(1000)
        cvd = _cvd(trades)
        if trades:
            avg_q = sum(float(t["q"]) for t in trades) / len(trades)
            cvd_norm = cvd / (avg_q * len(trades)) if avg_q else 0
            if cvd_norm > 0.10: s += 3; R.append(f"🔥 CVD buyers +{cvd_norm:.0%}")
            elif cvd_norm < -0.10: s -= 3; R.append(f"🔥 CVD sellers {cvd_norm:.0%}")
            elif cvd_norm > 0.03: s += 1
            elif cvd_norm < -0.03: s -= 1

        # OBV direction
        obv = _obv_dir(c1)
        if obv > 0: s += 1
        elif obv < 0: s -= 1
        S["order_flow"] = max(-10,min(10,s))

        # ═══════════════════════════════════════
        # 5. VOLUME (weight 2)
        # ═══════════════════════════════════════
        s = 0
        if len(c1) > 20:
            avg_v = sum(c.v for c in c1[-21:-1])/20
            cur_v = c1[-1].v
            vr = cur_v/avg_v if avg_v else 1
            if vr > 2.5:
                d = 1 if c1[-1].c>c1[-1].o else -1
                s += 4*d; R.append(f"🔥 Volume {vr:.1f}x {'↑' if d>0 else '↓'}")
            elif vr > 1.5:
                d = 1 if c1[-1].c>c1[-1].o else -1
                s += 2*d
        S["volume"] = max(-10,min(10,s))

        # ═══════════════════════════════════════
        # 6. MULTI-TIMEFRAME (weight 2)
        # ═══════════════════════════════════════
        s = 0
        for cl, name in [(cl5,"5m"),(cl15,"15m")]:
            if len(cl) > 21:
                e9 = _ema(cl,9); e21 = _ema(cl,21)
                if e9[-1]>e21[-1]: s += 2
                else: s -= 2
                r = _rsi(cl,14)
                if r > 55: s += 1
                elif r < 45: s -= 1
        if s >= 4: R.append("🔥 Multi-TF UP")
        elif s <= -4: R.append("🔥 Multi-TF DOWN")
        S["multi_tf"] = max(-10,min(10,s))

        # ═══════════════════════════════════════
        # 7. FUTURES HIDDEN DATA (weight 2.5)
        # ═══════════════════════════════════════
        s = 0

        # a) Funding rate — extreme = reversal signal
        fr = self.data.funding()
        if fr is not None:
            if fr > 0.0005: s -= 1; R.append(f"Funding +{fr*100:.3f}% (longs pay)")
            elif fr < -0.0005: s += 1; R.append(f"Funding {fr*100:.3f}% (shorts pay)")

        # b) Taker buy/sell
        takers = self.data.taker_buy_sell()
        if takers:
            latest = takers[-1]
            bv = float(latest.get("buyVol",0))
            sv = float(latest.get("sellVol",0))
            tot = bv+sv
            if tot:
                ratio = (bv-sv)/tot
                if ratio > 0.10: s += 3; R.append(f"🔥 Takers buying {ratio:.0%}")
                elif ratio < -0.10: s -= 3; R.append(f"🔥 Takers selling {abs(ratio):.0%}")
                elif ratio > 0.03: s += 1
                elif ratio < -0.03: s -= 1

        # c) Long/Short ratio trend
        ls_data = self.data.long_short_ratio()
        if len(ls_data) >= 3:
            ls_now = float(ls_data[-1]["longShortRatio"])
            ls_prev = float(ls_data[-3]["longShortRatio"])
            if ls_now > ls_prev * 1.05: s -= 1  # more longs → contrarian
            elif ls_now < ls_prev * 0.95: s += 1  # more shorts → contrarian
            if ls_now > 2.0: R.append(f"⚠ Crowded longs ({ls_now:.1f})")
            elif ls_now < 0.5: R.append(f"⚠ Crowded shorts ({ls_now:.1f})")

        # d) OI change — rising OI + price up = genuine, rising OI + price down = bearish
        oi_hist = self.data.oi_history()
        if len(oi_hist) >= 3:
            oi_now = float(oi_hist[-1]["sumOpenInterest"])
            oi_prev = float(oi_hist[-3]["sumOpenInterest"])
            oi_chg = (oi_now - oi_prev) / oi_prev * 100 if oi_prev else 0
            price_dir = 1 if cl1[-1] > cl1[-10] else -1
            if oi_chg > 1 and price_dir > 0:
                s += 2; R.append(f"OI rising + price ↑ (genuine)")
            elif oi_chg > 1 and price_dir < 0:
                s -= 2; R.append(f"OI rising + price ↓ (bearish)")
            elif oi_chg < -1:
                # Falling OI = positions closing
                s += 1 if price_dir > 0 else -1

        # e) Spot-Futures basis
        basis = self.data.spot_futures_spread()
        if basis > 5: s += 1; R.append(f"Futures premium +{basis:.0f}bps")
        elif basis < -5: s -= 1; R.append(f"Futures discount {basis:.0f}bps")

        # f) Liquidation proxy (volume spike on futures)
        liq_ratio, taker_buy_pct = self.data.liquidations_proxy()
        if liq_ratio > 3:
            if taker_buy_pct > 0.6:
                s += 2; R.append(f"🔥 Liq cascade — shorts squeezed")
            elif taker_buy_pct < 0.4:
                s -= 2; R.append(f"🔥 Liq cascade — longs rekt")

        S["futures"] = max(-10,min(10,s))

        # ═══════════════════════════════════════
        # WEIGHTED COMBINATION
        # ═══════════════════════════════════════
        W = {"trend":3, "momentum":3, "mean_rev":1.5,
             "order_flow":3, "volume":2, "multi_tf":2, "futures":2.5}

        raw = sum(S[k]*W[k] for k in S)
        max_raw = sum(10*w for w in W.values())  # 170

        # Map to 50-99
        abs_raw = abs(raw)
        confidence = 50 + (abs_raw / max_raw) * 49
        direction = "UP" if raw > 0 else "DOWN"

        # Conflict penalty
        if S.get("trend",0) * S.get("mean_rev",0) < -15:
            confidence *= 0.90

        # Agreement bonus
        agree = sum(1 for v in S.values() if (v>0)==(raw>0) and abs(v)>2)
        if agree >= 5: confidence = min(99, confidence * 1.05)

        confidence = max(50, min(99, confidence))

        # Score summary
        parts = " ".join(f"{k[0].upper()}:{S[k]:+.0f}" for k in S)
        R.append(f"[{parts} = {raw:+.0f}/{max_raw:.0f}]")

        # Window
        now = datetime.now(tz=timezone.utc)
        m = now.minute
        n5 = ((m//5)+1)*5
        if n5>=60: ws = now.replace(minute=0,second=0,microsecond=0)+timedelta(hours=1)
        else: ws = now.replace(minute=n5,second=0,microsecond=0)

        return Prediction(
            direction=direction,
            confidence=round(confidence,1),
            price=price,
            reasons=R,
            scores=S,
            window_start=ws,
            window_end=ws+timedelta(minutes=5),
        )


# ═══════════════════════════════════════════════════════
# TELEGRAM — sends EVERY prediction
# ═══════════════════════════════════════════════════════

class TG:
    def __init__(self):
        self.c = httpx.Client(timeout=10)
        self.sent = set()

    def send(self, p: Prediction):
        key = p.window_start.isoformat()
        if key in self.sent: return
        self.sent.add(key)

        # Tier
        if p.confidence >= 85: tier = "🎯🔥 SNIPER"
        elif p.confidence >= 75: tier = "🟢 STRONG"
        elif p.confidence >= 65: tier = "🟡 LEAN"
        else: tier = "⚪ COIN FLIP"

        d = "⬆️ UP" if p.direction=="UP" else "⬇️ DOWN"
        bar = "█"*int(p.confidence/10) + "░"*(10-int(p.confidence/10))

        ws = p.window_start - timedelta(hours=5)
        we = p.window_end - timedelta(hours=5)
        slug = f"btc-updown-5m-{int(p.window_start.timestamp())}"

        # Reasons (filtered)
        rl = "\n".join(f"  • {r}" for r in p.reasons if not r.startswith("["))
        # Score line
        sc = [r for r in p.reasons if r.startswith("[")]
        sc_line = sc[0] if sc else ""

        msg = f"""{tier}

{d}  |  {p.confidence}%
[{bar}]

⏰ {ws.strftime('%I:%M')}-{we.strftime('%I:%M %p')} ET
💰 BTC: ${p.price:,.2f}

{rl}

{sc_line}

🔗 https://polymarket.com/event/{slug}"""

        for cid in TELEGRAM_CHAT_IDS:
            try:
                self.c.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                            json={"chat_id":cid,"text":msg})
            except:
                pass
        print(f"    📢 {tier} {d} {p.confidence}% → TG ✅")

    def cleanup(self):
        if len(self.sent)>500: self.sent = set(list(self.sent)[-50:])


# ═══════════════════════════════════════════════════════
# MAIN — signal every 5 minutes, NO exceptions
# ═══════════════════════════════════════════════════════

def main():
    print("="*60)
    print("  🎯 BTC 5-MIN PREDICTOR v4 — ALWAYS SIGNALS")
    print("  Deep data: spot + futures + OI + liquidations + CVD")
    print("  Predicts 60s before every 5-min window")
    print("="*60)

    brain = Brain()
    tg = TG()
    scan = 0

    while True:
        try:
            scan += 1
            now = datetime.now(tz=timezone.utc)

            m = now.minute
            n5 = ((m//5)+1)*5
            if n5>=60: nw = now.replace(minute=0,second=0,microsecond=0)+timedelta(hours=1)
            else: nw = now.replace(minute=n5,second=0,microsecond=0)

            secs = (nw-now).total_seconds()
            slug = f"btc-updown-5m-{int(nw.timestamp())}"

            print(f"\n  [{now.strftime('%H:%M:%S')}] #{scan} | Next {nw.strftime('%H:%M')} in {secs:.0f}s")

            # Already sent for this window?
            if nw.isoformat() in tg.sent:
                print(f"    ✅ Done, waiting for next")
                time.sleep(max(secs+2, 10))
                continue

            # Wait until LEAD_TIME before window
            if secs > LEAD_TIME:
                wait = min(secs - LEAD_TIME, 30)
                print(f"    ⏳ {wait:.0f}s...")
                time.sleep(wait)
                continue

            # ── GO! Full analysis ──
            print(f"    🔍 Analyzing...")
            pred = brain.predict()

            print(f"    📊 {pred.direction} | {pred.confidence}% | ${pred.price:,.2f}")
            for r in pred.reasons[:8]:
                if not r.startswith("["): print(f"       {r}")

            # ALWAYS SEND
            tg.send(pred)
            tg.cleanup()

            # Wait for next window
            time.sleep(max(secs+2, 10))

        except KeyboardInterrupt:
            print("\n  Stopped.")
            break
        except Exception as e:
            print(f"    ❌ {e}")
            traceback.print_exc()
            time.sleep(10)


if __name__ == "__main__":
    main()
