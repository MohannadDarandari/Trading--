"""
============================================================
  Polymarket CLOB Simulation Engine v2
  RESEARCH / SIMULATION ONLY — NO LIVE TRADING
============================================================

Scans Polymarket orderbooks, detects edge between
Gamma-implied mid-prices and CLOB effective prices,
simulates outcomes after a delay, sends 2-hour reports
(tables + CSV) to Telegram.

Run:  py simulator/engine.py
Stop: Ctrl+C
"""

import requests
import json
import time
import csv
import io
import traceback
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
from pathlib import Path

# ─────────────────────────── Config ───────────────────────────

TELEGRAM_BOT_TOKEN = "8331165268:AAEA84wTDNeFuPhRJkjLiUqxxkaPEuL2B-o"
TELEGRAM_CHAT_IDS  = ["1688623770", "1675476723", "-5264145102"]

GAMMA_API  = "https://gamma-api.polymarket.com"
CLOB_API   = "https://clob.polymarket.com"

SCAN_INTERVAL_SEC    = 45
MARKET_LIMIT         = 60
MIN_VOLUME           = 200
EDGE_THRESHOLD       = 0.10        # 0.10% minimum edge to log
REPORT_INTERVAL_SEC  = 2 * 3600    # 2 hours
DELAY_CHECK_SEC      = 300         # 5 min to verify outcome
SIM_QUANTITY          = 10
VWAP_DEPTH           = 5

DATA_DIR = Path(__file__).parent.parent / "data" / "sim_reports"
DATA_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────────── Data Classes ─────────────────────

@dataclass
class Opportunity:
    timestamp: str
    market_slug: str
    question: str
    quantity: int
    best_ask_yes: float
    best_ask_no: float
    vwap_yes: float
    vwap_no: float
    unit_cost_signal: float
    edge_signal: float
    gamma_mid_yes: float = 0.0
    effective_bid_yes: float = 0.0
    effective_ask_yes: float = 0.0
    spread_pct: float = 0.0
    classification_after_delay: str = "PENDING"
    unit_cost_after_delay: float = 0.0
    simulated_profit: float = 0.0
    latency_ms: float = 0.0
    api_errors: int = 0
    edge_type: str = ""
    token_yes: str = ""
    token_no: str = ""
    check_at: float = 0.0


@dataclass
class MarketStats:
    market_slug: str = ""
    scans: int = 0
    opportunities: int = 0
    edges: List[float] = field(default_factory=list)
    successes: int = 0
    partials: int = 0
    liquidity_insufficient: int = 0
    simulated_pnl: float = 0.0


# ─────────────────────────── Telegram ─────────────────────────

class TelegramReporter:
    def __init__(self, token, chat_ids):
        self.token = token
        self.chat_ids = chat_ids if isinstance(chat_ids, list) else [chat_ids]
        self.base = f"https://api.telegram.org/bot{token}"

    def send_message(self, text, parse_mode="HTML"):
        for cid in self.chat_ids:
            for chunk in [text[i:i+4000] for i in range(0, len(text), 4000)]:
                try:
                    r = requests.post(f"{self.base}/sendMessage", json={
                        "chat_id": cid, "text": chunk,
                        "parse_mode": parse_mode}, timeout=15)
                    if not r.json().get("ok"):
                        print(f"[TG] Err ({cid}): {r.text[:200]}")
                except Exception as e:
                    print(f"[TG] {e}")
                time.sleep(0.5)

    def send_document(self, file_bytes, filename, caption=""):
        for cid in self.chat_ids:
            try:
                files = {"document": (filename, io.BytesIO(file_bytes), "text/csv")}
                data = {"chat_id": cid}
                if caption:
                    data["caption"] = caption[:1024]
                r = requests.post(f"{self.base}/sendDocument",
                                  data=data, files=files, timeout=30)
                if not r.json().get("ok"):
                    print(f"[TG] Doc err ({cid}): {r.text[:200]}")
            except Exception as e:
                print(f"[TG] Doc {e}")


# ─────────────────────────── CLOB Scanner ─────────────────────

class CLOBScanner:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "PolySimBot/2.0"
        self.markets_cache = []
        self.last_market_fetch = 0.0
        self.price_history = defaultdict(list)

    def refresh_markets(self):
        if time.time() - self.last_market_fetch < 90:
            return self.markets_cache
        try:
            r = self.session.get(f"{GAMMA_API}/markets", params={
                "limit": str(MARKET_LIMIT * 3),
                "active": "true", "closed": "false",
                "order": "volume", "ascending": "false",
            }, timeout=15)
            if r.status_code != 200:
                return self.markets_cache
            raw = r.json() if isinstance(r.json(), list) else r.json().get("data", [])
            filtered = []
            for m in raw:
                if not isinstance(m, dict):
                    continue
                vol = float(m.get("volume", 0) or 0)
                if vol < MIN_VOLUME:
                    continue
                raw_tids = m.get("clobTokenIds", "[]")
                try:
                    tids = json.loads(raw_tids) if isinstance(raw_tids, str) else raw_tids
                except:
                    tids = []
                if len(tids) < 2:
                    continue
                raw_op = m.get("outcomePrices", "[]")
                try:
                    ops = json.loads(raw_op) if isinstance(raw_op, str) else raw_op
                    gamma_yes = float(ops[0]) if ops else 0.5
                    gamma_no = float(ops[1]) if len(ops) > 1 else 1 - gamma_yes
                except:
                    gamma_yes, gamma_no = 0.5, 0.5
                m["_token_yes"] = tids[0]
                m["_token_no"] = tids[1]
                m["_gamma_yes"] = gamma_yes
                m["_gamma_no"] = gamma_no
                slug = m.get("slug", "?")[:20]
                self.price_history[slug].append((time.time(), gamma_yes))
                if len(self.price_history[slug]) > 200:
                    self.price_history[slug] = self.price_history[slug][-200:]
                filtered.append(m)
            self.markets_cache = filtered[:MARKET_LIMIT]
            self.last_market_fetch = time.time()
            print(f"[SCAN] Refreshed: {len(self.markets_cache)} markets")
        except Exception as e:
            print(f"[SCAN] Refresh err: {e}")
        return self.markets_cache

    def fetch_orderbook(self, token_id):
        try:
            r = self.session.get(f"{CLOB_API}/book",
                                 params={"token_id": token_id}, timeout=10)
            data = r.json()
            return None if "error" in data else data
        except:
            return None

    def _levels(self, raw):
        out = []
        for lvl in raw:
            try:
                p = float(lvl.get("price", 0))
                s = float(lvl.get("size", 0))
                if p > 0 and s > 0:
                    out.append((p, s))
            except:
                pass
        return out

    def _vwap(self, levels, depth=VWAP_DEPTH):
        tv, ts = 0.0, 0.0
        for p, s in levels[:depth]:
            tv += p * s
            ts += s
        return tv / ts if ts > 0 else 0.0

    def scan_market(self, market):
        t0 = time.time()
        slug = market.get("slug", "?")[:20]
        question = market.get("question", "?")
        gamma_yes = market.get("_gamma_yes", 0.5)
        gamma_no = market.get("_gamma_no", 0.5)
        tid_yes = market.get("_token_yes", "")
        tid_no = market.get("_token_no", "")
        errors = 0
        opps = []

        ob_yes = self.fetch_orderbook(tid_yes)
        if not ob_yes:
            return opps
        ob_no = self.fetch_orderbook(tid_no)
        if not ob_no:
            return opps

        yb = self._levels(ob_yes.get("bids", []))
        ya = self._levels(ob_yes.get("asks", []))
        nb = self._levels(ob_no.get("bids", []))
        na = self._levels(ob_no.get("asks", []))

        best_bid_y = yb[0][0] if yb else 0
        best_ask_y = ya[0][0] if ya else 1
        best_bid_n = nb[0][0] if nb else 0
        best_ask_n = na[0][0] if na else 1

        # Effective prices (cross-book)
        eff_ask_y = min(best_ask_y, (1 - best_bid_n) if best_bid_n > 0 else 1)
        eff_ask_n = min(best_ask_n, (1 - best_bid_y) if best_bid_y > 0 else 1)
        eff_bid_y = max(best_bid_y, (1 - best_ask_n) if best_ask_n < 1 else 0)

        vwap_y = self._vwap(ya) if ya else eff_ask_y
        vwap_n = self._vwap(na) if na else eff_ask_n

        spread_y = eff_ask_y - eff_bid_y
        spread_pct = (spread_y / gamma_yes * 100) if gamma_yes > 0.01 else 0
        latency = (time.time() - t0) * 1000
        unit_cost = eff_ask_y + eff_ask_n

        def _make(edge_pct, edge_type, cost_val):
            return Opportunity(
                timestamp=datetime.now(timezone.utc).strftime("%H:%M:%S"),
                market_slug=slug, question=question, quantity=SIM_QUANTITY,
                best_ask_yes=round(best_ask_y, 4),
                best_ask_no=round(best_ask_n, 4),
                vwap_yes=round(vwap_y, 4), vwap_no=round(vwap_n, 4),
                unit_cost_signal=round(cost_val, 4),
                edge_signal=round(edge_pct, 3),
                gamma_mid_yes=round(gamma_yes, 4),
                effective_bid_yes=round(eff_bid_y, 4),
                effective_ask_yes=round(eff_ask_y, 4),
                spread_pct=round(spread_pct, 2),
                edge_type=edge_type,
                latency_ms=round(latency, 1), api_errors=errors,
                token_yes=tid_yes, token_no=tid_no,
                check_at=time.time() + DELAY_CHECK_SEC)

        # Signal 1: Cross-book cost < 1
        if unit_cost < 1.0:
            e = (1 - unit_cost) * 100
            if e >= EDGE_THRESHOLD:
                opps.append(_make(e, "CROSS_BOOK", unit_cost))

        # Signal 2: Gamma divergence
        if 0.02 < gamma_yes < 0.98:
            if eff_ask_y < gamma_yes:
                e = (gamma_yes - eff_ask_y) * 100
                if e >= EDGE_THRESHOLD:
                    opps.append(_make(e, "GAMMA_DIV_Y", eff_ask_y))
            if eff_ask_n < gamma_no:
                e = (gamma_no - eff_ask_n) * 100
                if e >= EDGE_THRESHOLD:
                    opps.append(_make(e, "GAMMA_DIV_N", eff_ask_n))

        # Signal 3: Bid imbalance near mid
        bid_near = sum(s for p, s in yb if abs(p - gamma_yes) < 0.1)
        ask_near = sum(s for p, s in ya if abs(p - gamma_yes) < 0.1)
        if bid_near > 0 and ask_near > 0:
            imb = bid_near / (bid_near + ask_near)
            if imb > 0.75:
                e = (imb - 0.5) * 10
                if e >= EDGE_THRESHOLD:
                    opps.append(_make(e, "IMBALANCE", eff_ask_y))

        # Signal 4: Momentum (>1% move in 5 min)
        hist = self.price_history.get(slug, [])
        if len(hist) >= 3:
            cutoff = time.time() - 300
            old = [p for t, p in hist if t < cutoff]
            if old:
                delta_pct = abs(gamma_yes - old[-1]) * 100
                if delta_pct >= 1.0:
                    e = delta_pct * 0.3
                    if e >= EDGE_THRESHOLD:
                        opps.append(_make(e, "MOMENTUM", gamma_yes))

        return opps


# ─────────────────────────── Engine ───────────────────────────

class SimulationEngine:
    def __init__(self):
        self.scanner = CLOBScanner()
        self.tg = TelegramReporter(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_IDS)
        self.w_opps = []
        self.w_stats = defaultdict(MarketStats)
        self.w_start = time.time()
        self.d_opps = []
        self.d_stats = defaultdict(MarketStats)
        self.d_start = datetime.now(timezone.utc)
        self.pending = []
        self.total_scans = 0

    def run_forever(self):
        self.tg.send_message(
            "<b>🚀 Polymarket Sim Bot v2 Started</b>\n"
            f"📊 {MARKET_LIMIT} markets | ⏱ {SCAN_INTERVAL_SEC}s scans\n"
            f"📋 Reports every {REPORT_INTERVAL_SEC//3600}h | 🎯 Edge ≥ {EDGE_THRESHOLD}%\n"
            "<i>🔒 SIMULATION ONLY — NO LIVE ORDERS</i>")
        print("=" * 60)
        print("  POLYMARKET SIMULATION ENGINE v2")
        print("  NO LIVE TRADING — RESEARCH ONLY")
        print("=" * 60)
        while True:
            try:
                self._scan()
                self._check()
                self._maybe_report()
                self._maybe_daily()
                time.sleep(SCAN_INTERVAL_SEC)
            except KeyboardInterrupt:
                print("\n[ENGINE] Shutdown...")
                self._report(final=True)
                break
            except Exception as e:
                print(f"[ENGINE] {e}")
                traceback.print_exc()
                time.sleep(15)

    def _scan(self):
        mkts = self.scanner.refresh_markets()
        self.total_scans += 1
        found = 0
        for m in mkts:
            slug = m.get("slug", "?")[:20]
            self.w_stats[slug].market_slug = slug
            self.w_stats[slug].scans += 1
            self.d_stats[slug].market_slug = slug
            self.d_stats[slug].scans += 1
            for opp in self.scanner.scan_market(m):
                found += 1
                self.w_opps.append(opp)
                self.d_opps.append(opp)
                self.pending.append(opp)
                self.w_stats[slug].opportunities += 1
                self.w_stats[slug].edges.append(opp.edge_signal)
                self.d_stats[slug].opportunities += 1
                self.d_stats[slug].edges.append(opp.edge_signal)
            time.sleep(0.2)
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        print(f"[{ts}] Scan #{self.total_scans}: {len(mkts)} mkts, "
              f"{found} opps, {len(self.pending)} pend")

    def _check(self):
        now = time.time()
        still = []
        for opp in self.pending:
            if now < opp.check_at:
                still.append(opp)
                continue
            slug = opp.market_slug
            try:
                r = self.scanner.session.get(f"{GAMMA_API}/markets",
                    params={"slug": slug, "limit": "1"}, timeout=10)
                ml = r.json() if isinstance(r.json(), list) else r.json().get("data", [])
            except:
                ml = []
            if not ml:
                opp.classification_after_delay = "API_ERR"
                continue
            raw_op = ml[0].get("outcomePrices", "[]")
            try:
                ops = json.loads(raw_op) if isinstance(raw_op, str) else raw_op
                ng_y = float(ops[0]) if ops else opp.gamma_mid_yes
            except:
                ng_y = opp.gamma_mid_yes
            ng_n = 1 - ng_y

            ob_y = self.scanner.fetch_orderbook(opp.token_yes)
            ob_n = self.scanner.fetch_orderbook(opp.token_no)
            if ob_y and ob_n:
                ya = self.scanner._levels(ob_y.get("asks", []))
                na = self.scanner._levels(ob_n.get("asks", []))
                yb = self.scanner._levels(ob_y.get("bids", []))
                nb = self.scanner._levels(ob_n.get("bids", []))
                ea_y = min(ya[0][0] if ya else 1, (1 - nb[0][0]) if nb else 1)
                ea_n = min(na[0][0] if na else 1, (1 - yb[0][0]) if yb else 1)
                new_cost = ea_y + ea_n
                opp.unit_cost_after_delay = round(new_cost, 4)
            else:
                new_cost = 1.0

            # Classify
            if opp.edge_type == "GAMMA_DIV_Y":
                if ng_y > opp.unit_cost_signal:
                    opp.classification_after_delay = "SUCCESS"
                    opp.simulated_profit = round((ng_y - opp.unit_cost_signal) * opp.quantity, 4)
                elif ng_y > opp.unit_cost_signal * 0.995:
                    opp.classification_after_delay = "PARTIAL"
                    opp.simulated_profit = round(opp.edge_signal / 100 * opp.quantity * 0.3, 4)
                else:
                    opp.classification_after_delay = "LIQUIDITY"
            elif opp.edge_type == "GAMMA_DIV_N":
                if ng_n > opp.unit_cost_signal:
                    opp.classification_after_delay = "SUCCESS"
                    opp.simulated_profit = round((ng_n - opp.unit_cost_signal) * opp.quantity, 4)
                elif ng_n > opp.unit_cost_signal * 0.995:
                    opp.classification_after_delay = "PARTIAL"
                    opp.simulated_profit = round(opp.edge_signal / 100 * opp.quantity * 0.3, 4)
                else:
                    opp.classification_after_delay = "LIQUIDITY"
            elif opp.edge_type == "CROSS_BOOK":
                if new_cost < 1.0:
                    opp.classification_after_delay = "SUCCESS"
                    opp.simulated_profit = round((1 - new_cost) * opp.quantity, 4)
                else:
                    opp.classification_after_delay = "LIQUIDITY"
            else:
                move = abs(ng_y - opp.gamma_mid_yes) * 100
                if move >= opp.edge_signal * 0.5:
                    opp.classification_after_delay = "SUCCESS"
                    opp.simulated_profit = round(move / 100 * opp.quantity, 4)
                elif move > 0:
                    opp.classification_after_delay = "PARTIAL"
                    opp.simulated_profit = round(move / 100 * opp.quantity * 0.5, 4)
                else:
                    opp.classification_after_delay = "LIQUIDITY"

            ws = self.w_stats[slug]
            ds = self.d_stats[slug]
            cl = opp.classification_after_delay
            if cl == "SUCCESS":
                ws.successes += 1; ds.successes += 1
                ws.simulated_pnl += opp.simulated_profit
                ds.simulated_pnl += opp.simulated_profit
            elif cl == "PARTIAL":
                ws.partials += 1; ds.partials += 1
                ws.simulated_pnl += opp.simulated_profit
                ds.simulated_pnl += opp.simulated_profit
            else:
                ws.liquidity_insufficient += 1
                ds.liquidity_insufficient += 1
            time.sleep(0.3)
        self.pending = still

    def _maybe_report(self):
        if time.time() - self.w_start >= REPORT_INTERVAL_SEC:
            self._report()

    def _maybe_daily(self):
        now = datetime.now(timezone.utc)
        if now.date() > self.d_start.date():
            self._daily_report()
            self.d_start = now
            self.d_opps.clear()
            self.d_stats.clear()

    def _report(self, final=False):
        label = "FINAL" if final else "2-HOUR"
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        total = len(self.w_opps)

        lines = [f"<b>📊 {label} REPORT — {now}</b>",
                 f"Scans: {self.total_scans} | Opps: {total}\n"]

        hdr = f"{'Market':<14}|{'Opp':>4}|{'AvE%':>5}|{'MxE%':>5}|{'Su%':>4}|{'Pa%':>4}|{'Li%':>4}|{'$Sim':>6}"
        rows = [f"<pre>{hdr}", "-" * len(hdr)]
        for sl, st in sorted(self.w_stats.items(),
                              key=lambda x: x[1].opportunities, reverse=True):
            if st.opportunities == 0:
                continue
            ae = sum(st.edges) / len(st.edges) if st.edges else 0
            me = max(st.edges) if st.edges else 0
            tc = st.successes + st.partials + st.liquidity_insufficient
            sp = (st.successes / tc * 100) if tc else 0
            pp = (st.partials / tc * 100) if tc else 0
            lp = (st.liquidity_insufficient / tc * 100) if tc else 0
            rows.append(f"{sl[:14]:<14}|{st.opportunities:>4}|{ae:>5.2f}|{me:>5.2f}|"
                        f"{sp:>3.0f}%|{pp:>3.0f}%|{lp:>3.0f}%|{st.simulated_pnl:>5.2f}")
        if len(rows) == 2:
            rows.append("  (no opportunities)")
        rows.append("</pre>")
        lines.append("\n".join(rows))

        cl = [o for o in self.w_opps if o.classification_after_delay != "PENDING"]
        top10 = sorted(cl, key=lambda x: x.edge_signal, reverse=True)[:10]
        if top10:
            lines.append(f"\n<b>TOP 10 OPPORTUNITIES</b>")
            th = f"{'Time':>8}|{'Market':<14}|{'Q':>2}|{'Cost':>6}|{'E%':>5}|{'AkY':>5}|{'AkN':>5}|{'Type':>8}|{'Cls':>8}"
            tr = [f"<pre>{th}", "-" * len(th)]
            for o in top10:
                tr.append(f"{o.timestamp:>8}|{o.market_slug[:14]:<14}|{o.quantity:>2}|"
                          f"{o.unit_cost_signal:>6.3f}|{o.edge_signal:>4.1f}%|"
                          f"{o.best_ask_yes:>5.3f}|{o.best_ask_no:>5.3f}|"
                          f"{o.edge_type[:8]:>8}|{o.classification_after_delay[:8]:>8}")
            tr.append("</pre>")
            lines.append("\n".join(tr))

        lines.append("\n<i>🔒 SIMULATION ONLY — NO LIVE ORDERS</i>")
        self.tg.send_message("\n".join(lines))

        ts_f = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
        dc = self._csv_d(self.w_opps)
        self.tg.send_document(dc.encode(), f"opps_{ts_f}.csv", f"Opportunities — {now}")
        sc = self._csv_s(self.w_stats)
        self.tg.send_document(sc.encode(), f"summary_{ts_f}.csv", f"Summary — {now}")
        (DATA_DIR / f"opps_{ts_f}.csv").write_text(dc, encoding="utf-8")
        (DATA_DIR / f"summary_{ts_f}.csv").write_text(sc, encoding="utf-8")
        self.w_opps.clear()
        self.w_stats.clear()
        self.w_start = time.time()
        print(f"[REPORT] {label} sent ✅")

    def _daily_report(self):
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        tp = sum(s.simulated_pnl for s in self.d_stats.values())
        lines = [f"<b>📈 DAILY — {now}</b>",
                 f"Opps: {len(self.d_opps)} | Sim PnL: <b>${tp:.2f}</b>\n"]
        hdr = f"{'Market':<14}|{'Opp':>4}|{'AvE%':>5}|{'Su%':>4}|{'$Sim':>6}"
        rows = [f"<pre>{hdr}", "-" * len(hdr)]
        for sl, st in sorted(self.d_stats.items(),
                              key=lambda x: x[1].simulated_pnl, reverse=True)[:20]:
            if st.opportunities == 0:
                continue
            ae = sum(st.edges) / len(st.edges) if st.edges else 0
            tc = st.successes + st.partials + st.liquidity_insufficient
            sp = (st.successes / tc * 100) if tc else 0
            rows.append(f"{sl[:14]:<14}|{st.opportunities:>4}|{ae:>5.2f}|{sp:>3.0f}%|{st.simulated_pnl:>5.2f}")
        rows.append("</pre>")
        lines.append("\n".join(rows))
        lines.append("<i>🔒 SIMULATION ONLY</i>")
        self.tg.send_message("\n".join(lines))
        ts = datetime.now(timezone.utc).strftime("%Y%m%d")
        self.tg.send_document(self._csv_d(self.d_opps).encode(), f"daily_opps_{ts}.csv")
        self.tg.send_document(self._csv_s(self.d_stats).encode(), f"daily_summary_{ts}.csv")
        print(f"[REPORT] Daily sent ✅")

    @staticmethod
    def _csv_d(opps):
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["timestamp", "market", "Q", "best_ask_yes", "best_ask_no",
                     "vwap_yes", "vwap_no", "unit_cost_signal", "edge_signal",
                     "edge_type", "gamma_mid_yes", "spread_pct",
                     "classification_after_delay", "unit_cost_after_delay",
                     "simulated_profit", "latency_ms", "api_errors"])
        for o in opps:
            w.writerow([o.timestamp, o.market_slug, o.quantity,
                        o.best_ask_yes, o.best_ask_no, o.vwap_yes, o.vwap_no,
                        o.unit_cost_signal, o.edge_signal, o.edge_type,
                        o.gamma_mid_yes, o.spread_pct,
                        o.classification_after_delay, o.unit_cost_after_delay,
                        o.simulated_profit, o.latency_ms, o.api_errors])
        return buf.getvalue()

    @staticmethod
    def _csv_s(stats):
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["market", "scans", "opportunities", "avg_edge", "max_edge",
                     "success_rate", "partial_rate", "liquidity_rate", "simulated_pnl"])
        for sl, st in sorted(stats.items(),
                              key=lambda x: x[1].opportunities, reverse=True):
            if st.opportunities == 0:
                continue
            ae = sum(st.edges) / len(st.edges) if st.edges else 0
            me = max(st.edges) if st.edges else 0
            tc = st.successes + st.partials + st.liquidity_insufficient
            s = (st.successes / tc * 100) if tc else 0
            p = (st.partials / tc * 100) if tc else 0
            l = (st.liquidity_insufficient / tc * 100) if tc else 0
            w.writerow([sl, st.scans, st.opportunities,
                        round(ae, 3), round(me, 3),
                        round(s, 1), round(p, 1), round(l, 1),
                        round(st.simulated_pnl, 4)])
        return buf.getvalue()


if __name__ == "__main__":
    engine = SimulationEngine()
    engine.run_forever()
