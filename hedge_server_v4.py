#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║      🦞 PolyClaw Hedge Server v4 — Full Execution Engine        ║
║      v3 Scanners + CLOB Execution + Kill Switches + SQLite      ║
║      + VWAP Depth Check — The Complete Money Machine             ║
╚══════════════════════════════════════════════════════════════════╝

UPGRADES from v3:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• ClobClientWrapper — live order execution via py-clob-client (EIP-712)
• Kill Switches — 7 safety kill conditions from structural_bot
• SQLite Logging — every scan, order, fill, incident persisted
• VWAP Depth Check — verifies order book liquidity before execution

SCANNERS (unchanged from v3):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. EVENT GROUP ARBITRAGE
2. THRESHOLD MISPRICING SCANNER
3. KNOWN PATTERN MONITOR
"""

import os
import sys
import json
import time
import sqlite3
import asyncio
import platform
import traceback
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional, Iterable, Tuple

import httpx

# PolyClaw imports
sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from lib.gamma_client import GammaClient, Market, MarketGroup
from lib.clob_client import ClobClientWrapper
from lib.wallet_manager import WalletManager


# =============================================================================
# CONFIGURATION
# =============================================================================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8331165268:AAEA84wTDNeFuPhRJkjLiUqxxkaPEuL2B-o")
TELEGRAM_CHAT_IDS = json.loads(os.getenv("TELEGRAM_CHAT_IDS", '["1688623770","1675476723","-5264145102"]'))

SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL", "180"))  # 3 min between scans
SUMMARY_INTERVAL = int(os.getenv("SUMMARY_INTERVAL", "900"))  # 15 min

# Event group safety filters
MIN_EVENT_VOLUME_24H = float(os.getenv("MIN_EVENT_VOLUME_24H", "5000"))

# Trading
MIN_PROFIT_PER_DOLLAR = float(os.getenv("MIN_PROFIT", "0.003"))  # $0.003 min profit per $1
AUTO_TRADE = os.getenv("AUTO_TRADE", "false").lower() == "true"
TRADE_BUDGET = float(os.getenv("TRADE_BUDGET", "50"))  # $ per trade
BANKROLL = float(os.getenv("BANKROLL", "100"))  # Total bankroll

# Fee on Polymarket (approximately)
POLY_FEE = 0.02  # ~2% estimated fee per side

# Re-alert threshold (profit change %)
REALERT_THRESHOLD = 0.05

# VWAP / Depth settings
MAX_SPREAD = float(os.getenv("MAX_SPREAD", "0.05"))  # Max bid-ask spread
MIN_DEPTH_USD = float(os.getenv("MIN_DEPTH_USD", "20"))  # Min ask depth in USD

# Kill switch limits
KILL_PARTIAL_FILL_STREAK = int(os.getenv("KILL_PARTIAL_FILL_STREAK", "3"))
KILL_PARTIAL_FILL_DAY = int(os.getenv("KILL_PARTIAL_FILL_DAY", "8"))
KILL_API_ERRORS_10M = int(os.getenv("KILL_API_ERRORS_10M", "5"))
KILL_LATENCY_MS = float(os.getenv("KILL_LATENCY_MS", "4000"))
KILL_LATENCY_WINDOW_SEC = int(os.getenv("KILL_LATENCY_WINDOW_SEC", "120"))
KILL_THIN_BOOK_SCANS = int(os.getenv("KILL_THIN_BOOK_SCANS", "4"))
KILL_MAX_TRADES_PER_HOUR = int(os.getenv("KILL_MAX_TRADES_PER_HOUR", "20"))
KILL_MAX_EXPOSURE_PCT = float(os.getenv("KILL_MAX_EXPOSURE_PCT", "0.5"))

# State files
STATE_DIR = Path(__file__).parent / "data"
PATTERNS_FILE = STATE_DIR / "discovered_patterns.json"
HISTORY_FILE = STATE_DIR / "hedge_history.json"
DB_FILE = STATE_DIR / "hedge_bot.db"


# =============================================================================
# ASSET THRESHOLDS FOR AUTO-DISCOVERY
# =============================================================================

THRESHOLD_ASSETS = {
    "Bitcoin": {
        "search_terms": ["Bitcoin above", "Bitcoin reach", "BTC above"],
        "levels": [50000, 55000, 60000, 65000, 68000, 70000, 72000, 75000,
                   80000, 85000, 90000, 95000, 100000, 110000, 120000, 150000],
    },
    "Ethereum": {
        "search_terms": ["Ethereum above", "ETH above", "Ethereum reach"],
        "levels": [2000, 2500, 3000, 3500, 4000, 4500, 5000, 6000],
    },
    "Solana": {
        "search_terms": ["Solana above", "SOL above", "Solana reach", "Solana dip"],
        "levels": [100, 150, 200, 250, 300, 400, 500],
    },
    "XRP": {
        "search_terms": ["XRP above", "XRP reach"],
        "levels": [1, 2, 3, 5, 10],
    },
    "AAPL": {
        "search_terms": ["AAPL above", "AAPL close above", "Apple stock"],
        "levels": [200, 225, 250, 275, 285, 300],
    },
    "META": {
        "search_terms": ["META above", "META close above"],
        "levels": [500, 550, 600, 640, 700],
    },
    "PLTR": {
        "search_terms": ["PLTR above", "PLTR close above", "Palantir"],
        "levels": [80, 100, 120, 128, 150],
    },
    "GOOGL": {
        "search_terms": ["GOOGL above", "GOOGL close above", "Google stock"],
        "levels": [150, 175, 200, 225],
    },
    "NVDA": {
        "search_terms": ["NVDA above", "NVDA close above", "Nvidia stock"],
        "levels": [100, 120, 140, 150, 160, 180, 200],
    },
}

# Known hedge patterns from AI research
KNOWN_PATTERNS = [
    {
        "name": "Fed Rates: Decrease vs Increase",
        "search_a": "Fed decrease interest rates",
        "search_b": "Fed increase interest rates",
        "hedge_type": "complementary",
        "desc": "Fed can decrease OR increase. Buy YES decrease + NO increase.",
    },
    {
        "name": "Fed Rates: No Change vs Increase",
        "search_a": "no change in Fed interest rates",
        "search_b": "Fed increase interest rates",
        "hedge_type": "complementary",
        "desc": "If Fed doesn't change, they won't increase.",
    },
    {
        "name": "Trump Nom: Shelton vs No One",
        "search_a": "Trump nominate Judy Shelton",
        "search_b": "Trump nominate no one",
        "hedge_type": "exclusive",
        "desc": "Can't nominate Shelton AND no one at the same time.",
    },
    {
        "name": "Trump Nom: Miran vs No One",
        "search_a": "Trump nominate Stephen Miran",
        "search_b": "Trump nominate no one",
        "hedge_type": "exclusive",
        "desc": "Can't nominate Miran AND no one at the same time.",
    },
    {
        "name": "Iran Strike Timeframe",
        "search_a": "strikes Iran by February",
        "search_b": "strikes Iran by March",
        "hedge_type": "superset",
        "desc": "Strike by Feb → Strike by March too. Hedge: YES(March) + NO(Feb).",
    },
]


# =============================================================================
# VWAP DEPTH CHECK (from structural_bot/vwap.py)
# =============================================================================

def vwap_cost(levels: Iterable[Tuple[float, float]], qty: float) -> tuple[float, bool]:
    """Return total cost to buy qty across ask levels and whether depth is sufficient."""
    if qty <= 0:
        return 0.0, False

    remaining = qty
    cost = 0.0
    for price, size in levels:
        if size <= 0:
            continue
        take = min(remaining, size)
        cost += take * price
        remaining -= take
        if remaining <= 0:
            return cost, True

    return cost, False


def best_spread(bids: Iterable[Tuple[float, float]], asks: Iterable[Tuple[float, float]]) -> float:
    """Return best ask - best bid, or a large number if not available."""
    try:
        best_bid = max(bids, key=lambda x: x[0])[0]
        best_ask = min(asks, key=lambda x: x[0])[0]
        return best_ask - best_bid
    except Exception:
        return 999.0


# =============================================================================
# KILL SWITCH / RISK MANAGER (from structural_bot/risk.py)
# =============================================================================

@dataclass
class RiskLimits:
    max_open_exposure_pct: float = KILL_MAX_EXPOSURE_PCT
    max_trades_per_hour: int = KILL_MAX_TRADES_PER_HOUR
    partial_fill_streak_kill: int = KILL_PARTIAL_FILL_STREAK
    partial_fill_day_kill: int = KILL_PARTIAL_FILL_DAY
    api_error_kill_10m: int = KILL_API_ERRORS_10M
    latency_kill_ms: float = KILL_LATENCY_MS
    latency_kill_window_sec: int = KILL_LATENCY_WINDOW_SEC
    thin_book_kill_scans: int = KILL_THIN_BOOK_SCANS


class RiskManager:
    """7 kill switches to protect the bot from runaway losses."""

    def __init__(self, limits: Optional[RiskLimits] = None):
        self.limits = limits or RiskLimits()
        self.partial_fill_streak = 0
        self.partial_fill_day = 0
        self.api_errors_10m: list[float] = []
        self.latency_window: list[tuple[float, float]] = []
        self.thin_book_streak = 0
        self.trades_last_hour: list[float] = []
        self.kill_reason = ""
        self.current_open_exposure = 0.0
        self.killed = False  # Latched kill state

    def record_partial_fill(self) -> None:
        self.partial_fill_streak += 1
        self.partial_fill_day += 1

    def record_hedged_complete(self) -> None:
        self.partial_fill_streak = 0

    def record_api_error(self) -> None:
        now = time.time()
        self.api_errors_10m.append(now)
        self.api_errors_10m = [t for t in self.api_errors_10m if now - t <= 600]

    def record_latency(self, ms: float) -> None:
        now = time.time()
        self.latency_window.append((now, ms))
        self.latency_window = [
            (t, v) for t, v in self.latency_window
            if now - t <= self.limits.latency_kill_window_sec
        ]

    def record_thin_book(self, thin: bool) -> None:
        if thin:
            self.thin_book_streak += 1
        else:
            self.thin_book_streak = 0

    def record_trade(self) -> None:
        now = time.time()
        self.trades_last_hour.append(now)
        self.trades_last_hour = [t for t in self.trades_last_hour if now - t <= 3600]

    def add_exposure(self, exposure: float) -> None:
        self.current_open_exposure += exposure

    def reduce_exposure(self, exposure: float) -> None:
        self.current_open_exposure = max(0.0, self.current_open_exposure - exposure)

    def can_take_trade(self, bankroll: float, exposure_add: float) -> bool:
        """Check if adding this exposure would exceed limits."""
        if bankroll <= 0:
            return False
        projected = self.current_open_exposure + exposure_add
        return projected <= bankroll * self.limits.max_open_exposure_pct

    def should_kill(self) -> bool:
        """Check all 7 kill conditions. Returns True if bot should stop trading."""
        if self.partial_fill_streak >= self.limits.partial_fill_streak_kill:
            self.kill_reason = f"partial_fill_streak ({self.partial_fill_streak})"
            self.killed = True
            return True
        if self.partial_fill_day >= self.limits.partial_fill_day_kill:
            self.kill_reason = f"partial_fill_day ({self.partial_fill_day})"
            self.killed = True
            return True
        if len(self.api_errors_10m) >= self.limits.api_error_kill_10m:
            self.kill_reason = f"api_errors ({len(self.api_errors_10m)} in 10m)"
            self.killed = True
            return True
        if self.thin_book_streak >= self.limits.thin_book_kill_scans:
            self.kill_reason = f"thin_book_streak ({self.thin_book_streak})"
            self.killed = True
            return True
        if self.latency_window:
            avg_latency = sum(v for _, v in self.latency_window) / len(self.latency_window)
            if avg_latency >= self.limits.latency_kill_ms:
                self.kill_reason = f"latency ({avg_latency:.0f}ms avg)"
                self.killed = True
                return True
        if len(self.trades_last_hour) >= self.limits.max_trades_per_hour:
            self.kill_reason = f"max_trades_per_hour ({len(self.trades_last_hour)})"
            self.killed = True
            return True
        return False

    def status_text(self) -> str:
        """Human-readable status."""
        lines = [
            f"  Partial fills (streak/day): {self.partial_fill_streak}/{self.partial_fill_day}",
            f"  API errors (10m): {len(self.api_errors_10m)}",
            f"  Thin book streak: {self.thin_book_streak}",
            f"  Trades (1h): {len(self.trades_last_hour)}",
            f"  Open exposure: ${self.current_open_exposure:.2f}",
        ]
        if self.latency_window:
            avg = sum(v for _, v in self.latency_window) / len(self.latency_window)
            lines.append(f"  Avg latency: {avg:.0f}ms")
        if self.killed:
            lines.append(f"  ⛔ KILLED: {self.kill_reason}")
        return "\n".join(lines)


# =============================================================================
# SQLITE LOGGING (adapted from structural_bot/db.py)
# =============================================================================

HEDGE_DB_SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        scan_number INTEGER,
        scanner TEXT,
        markets_checked INTEGER DEFAULT 0,
        opportunities_found INTEGER DEFAULT 0,
        latency_ms REAL,
        error TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS opportunities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        name TEXT NOT NULL,
        scanner TEXT,
        hedge_type TEXT,
        total_cost REAL,
        min_payout REAL,
        guaranteed_profit REAL,
        net_profit_per_dollar REAL,
        confidence TEXT,
        market_ids TEXT,
        executed INTEGER DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        opportunity_name TEXT,
        market_id TEXT NOT NULL,
        token_id TEXT,
        side TEXT NOT NULL,
        price REAL,
        size REAL,
        order_id TEXT,
        status TEXT,
        error TEXT,
        latency_ms REAL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS fills (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        order_id TEXT,
        market_id TEXT NOT NULL,
        side TEXT NOT NULL,
        price REAL,
        size REAL,
        fee_est REAL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS incidents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        incident_type TEXT NOT NULL,
        details TEXT,
        kill_reason TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS depth_checks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        token_id TEXT NOT NULL,
        spread REAL,
        ask_depth_usd REAL,
        vwap_cost REAL,
        depth_ok INTEGER,
        spread_ok INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS pnl (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        trade_budget REAL,
        exposure REAL,
        realized REAL DEFAULT 0,
        notes TEXT
    )
    """,
]


class HedgeDB:
    """SQLite database for hedge bot logging."""

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        cur = self.conn.cursor()
        for ddl in HEDGE_DB_SCHEMA:
            cur.execute(ddl)
        self.conn.commit()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def log_scan(self, scan_number: int, scanner: str, markets_checked: int,
                 opportunities_found: int, latency_ms: float, error: str = "") -> None:
        self.conn.execute(
            "INSERT INTO scans (ts, scan_number, scanner, markets_checked, opportunities_found, latency_ms, error) "
            "VALUES (?,?,?,?,?,?,?)",
            (self._now(), scan_number, scanner, markets_checked, opportunities_found, latency_ms, error),
        )
        self.conn.commit()

    def log_opportunity(self, opp: 'HedgeOpportunity', executed: bool = False) -> None:
        market_ids = json.dumps([m["id"] for m in opp.markets])
        self.conn.execute(
            "INSERT INTO opportunities (ts, name, scanner, hedge_type, total_cost, min_payout, "
            "guaranteed_profit, net_profit_per_dollar, confidence, market_ids, executed) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (self._now(), opp.name, opp.scanner, opp.hedge_type, opp.total_cost,
             opp.min_payout, opp.guaranteed_profit, opp.net_profit_per_dollar,
             opp.confidence, market_ids, int(executed)),
        )
        self.conn.commit()

    def log_order(self, opp_name: str, market_id: str, token_id: str, side: str,
                  price: float, size: float, order_id: str = "", status: str = "",
                  error: str = "", latency_ms: float = 0) -> None:
        self.conn.execute(
            "INSERT INTO orders (ts, opportunity_name, market_id, token_id, side, price, size, "
            "order_id, status, error, latency_ms) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (self._now(), opp_name, market_id, token_id, side, price, size,
             order_id, status, error, latency_ms),
        )
        self.conn.commit()

    def log_incident(self, incident_type: str, details: str = "", kill_reason: str = "") -> None:
        self.conn.execute(
            "INSERT INTO incidents (ts, incident_type, details, kill_reason) VALUES (?,?,?,?)",
            (self._now(), incident_type, details, kill_reason),
        )
        self.conn.commit()

    def log_depth_check(self, token_id: str, spread: float, ask_depth_usd: float,
                        vwap: float, depth_ok: bool, spread_ok: bool) -> None:
        self.conn.execute(
            "INSERT INTO depth_checks (ts, token_id, spread, ask_depth_usd, vwap_cost, depth_ok, spread_ok) "
            "VALUES (?,?,?,?,?,?,?)",
            (self._now(), token_id, spread, ask_depth_usd, vwap, int(depth_ok), int(spread_ok)),
        )
        self.conn.commit()

    def log_pnl(self, budget: float, exposure: float, realized: float = 0, notes: str = "") -> None:
        self.conn.execute(
            "INSERT INTO pnl (ts, trade_budget, exposure, realized, notes) VALUES (?,?,?,?,?)",
            (self._now(), budget, exposure, realized, notes),
        )
        self.conn.commit()

    def get_stats(self) -> dict:
        """Get summary stats for status reports."""
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) as cnt FROM scans")
        total_scans = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(*) as cnt FROM opportunities")
        total_opps = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(*) as cnt FROM orders WHERE status='filled'")
        total_fills = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(*) as cnt FROM orders WHERE error != '' AND error IS NOT NULL")
        total_errors = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(*) as cnt FROM incidents")
        total_incidents = cur.fetchone()["cnt"]
        return {
            "total_scans": total_scans,
            "total_opps": total_opps,
            "total_fills": total_fills,
            "total_errors": total_errors,
            "total_incidents": total_incidents,
        }


# =============================================================================
# TELEGRAM BOT
# =============================================================================

class Telegram:
    def __init__(self):
        self.url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

    async def send(self, msg: str):
        """Send message to all chat IDs."""
        async with httpx.AsyncClient(timeout=30) as c:
            for cid in TELEGRAM_CHAT_IDS:
                try:
                    await c.post(f"{self.url}/sendMessage", json={
                        "chat_id": cid, "text": msg[:4096],
                        "parse_mode": "HTML", "disable_web_page_preview": True,
                    })
                except Exception as e:
                    print(f"  [TG] Error {cid}: {e}", flush=True)

    async def startup(self, scanner_info: str, risk_info: str):
        now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
        await self.send(
            "🦞 <b>PolyClaw Hedge Server v4 ONLINE</b>\n"
            "<i>CLOB Execution + Kill Switches + SQLite + VWAP</i>\n\n"
            f"⏰ {now}\n"
            f"🔄 Scan every: {SCAN_INTERVAL//60} min\n"
            f"🤖 Auto-trade: {'ON ✅' if AUTO_TRADE else 'OFF (alerts only)'}\n"
            f"💰 Budget: ${TRADE_BUDGET:.0f}/trade | Bankroll: ${BANKROLL:.0f}\n"
            f"📊 Fee estimate: {POLY_FEE*100:.0f}%\n"
            f"🛡 Max spread: {MAX_SPREAD*100:.1f}% | Min depth: ${MIN_DEPTH_USD:.0f}\n\n"
            f"{scanner_info}\n\n"
            f"<b>⛔ Kill Switches:</b>\n{risk_info}\n"
            "━━━━━━━━━━━━━━━━━━━━━"
        )


# =============================================================================
# HEDGE OPPORTUNITY
# =============================================================================

@dataclass
class HedgeOpportunity:
    """A discovered hedge opportunity with full details."""
    name: str
    scanner: str  # "event_group" | "threshold" | "known_pattern"
    hedge_type: str  # "group_arb" | "threshold" | "complementary" | "exclusive" | "superset"

    # Markets involved
    markets: list[dict]  # [{id, question, position, price, token_id, volume}]

    total_cost: float  # Total cost to enter all legs
    min_payout: float  # Minimum guaranteed payout
    max_payout: float  # Maximum possible payout
    guaranteed_profit: float  # min_payout - total_cost (per $1 invested)
    best_case_profit: float  # max_payout - total_cost

    # After fees
    net_profit_per_dollar: float
    confidence: str  # "GUARANTEED" | "HIGH" | "MEDIUM"

    # Timestamps
    discovered_at: str = ""
    last_price: float = 0.0

    def alert_key(self) -> str:
        return "|".join(sorted(m["id"] for m in self.markets))

    def trade_instructions(self, budget: float) -> str:
        """Generate exact trade instructions."""
        if self.total_cost <= 0:
            return "⚠️ Invalid pricing"

        scale = budget / self.total_cost
        lines = []
        for m in self.markets:
            amount = m["price"] * scale
            lines.append(
                f"  → Buy {m['position']} on \"{m['question'][:50]}\"\n"
                f"    Price: ${m['price']:.4f} | Amount: ${amount:.2f}"
            )

        min_return = self.min_payout * scale
        max_return = self.max_payout * scale
        net_profit = (self.min_payout - self.total_cost) * scale
        net_after_fees = net_profit - (budget * POLY_FEE * 2)

        lines.append(f"\n  💰 Total invest: ${budget:.2f}")
        lines.append(f"  📈 Min return: ${min_return:.2f}")
        lines.append(f"  🎯 Max return: ${max_return:.2f}")
        lines.append(f"  💵 Min profit: ${net_profit:.2f}")
        lines.append(f"  💵 After fees (~{POLY_FEE*200:.0f}%): ${net_after_fees:.2f}")

        return "\n".join(lines)


# =============================================================================
# SCANNER 1: EVENT GROUP ARBITRAGE
# =============================================================================

class EventGroupScanner:
    """
    Scans event groups for arbitrage opportunities.
    If an event has mutually exclusive outcomes and sum(YES prices) < 1,
    buying YES on all outcomes guarantees profit.
    """

    def __init__(self, gamma: GammaClient):
        self.gamma = gamma

    def _is_exclusive_event(self, event: MarketGroup, markets: list[Market]) -> bool:
        title = (event.title or "").lower()
        desc = (event.description or "").lower()
        keywords = [
            "winner", "nominee", "who will", "which", "election", "primary",
            "champion", "win", "wins", "best", "award", "oscar", "grammy",
            "world cup", "super bowl", "nba", "nhl", "ufc", "formula 1",
        ]

        text_match = any(k in title or k in desc for k in keywords)
        if not text_match:
            return False

        total_yes = sum(m.yes_price for m in markets)
        if total_yes < 0.8 or total_yes > 1.2:
            return False

        return True

    async def scan(self) -> tuple[list[HedgeOpportunity], int]:
        """Scan event groups for arbitrage. Returns (opportunities, markets_checked)."""
        opportunities = []
        markets_checked = 0

        try:
            events = await self.gamma.get_events(limit=50)
        except Exception as e:
            print(f"  [EventGroup] Error fetching events: {e}", flush=True)
            return [], 0

        for event in events:
            active_markets = [m for m in event.markets if m.active and not m.closed and not m.resolved]
            markets_checked += len(active_markets)

            if len(active_markets) < 2:
                continue

            if not self._is_exclusive_event(event, active_markets):
                continue

            total_volume = sum(m.volume_24h for m in active_markets)
            if total_volume < MIN_EVENT_VOLUME_24H:
                continue

            if len(active_markets) < 3:
                continue

            # Strategy 1: Sum of YES prices < 1 (buy all YES)
            total_yes = sum(m.yes_price for m in active_markets)
            if total_yes > 0 and total_yes < (1.0 - MIN_PROFIT_PER_DOLLAR - POLY_FEE * 2):
                profit_per_dollar = (1.0 - total_yes) / total_yes
                net_profit = profit_per_dollar - POLY_FEE * 2

                if net_profit > MIN_PROFIT_PER_DOLLAR:
                    markets_info = []
                    for m in active_markets:
                        markets_info.append({
                            "id": m.id, "question": m.question, "position": "YES",
                            "price": m.yes_price, "token_id": m.yes_token_id,
                            "volume": m.volume_24h,
                        })

                    opp = HedgeOpportunity(
                        name=f"📦 {event.title[:40]}", scanner="event_group",
                        hedge_type="group_arb", markets=markets_info,
                        total_cost=total_yes, min_payout=1.0, max_payout=1.0,
                        guaranteed_profit=1.0 - total_yes,
                        best_case_profit=1.0 - total_yes,
                        net_profit_per_dollar=net_profit, confidence="GUARANTEED",
                    )
                    opportunities.append(opp)

            # Strategy 2: Sum of NO prices < 1
            total_no = sum(m.no_price for m in active_markets)
            if total_no > 0 and total_no < (1.0 - MIN_PROFIT_PER_DOLLAR - POLY_FEE * 2):
                profit_per_dollar = (1.0 - total_no) / total_no
                net_profit = profit_per_dollar - POLY_FEE * 2

                if net_profit > MIN_PROFIT_PER_DOLLAR:
                    markets_info = []
                    for m in active_markets:
                        markets_info.append({
                            "id": m.id, "question": m.question, "position": "NO",
                            "price": m.no_price, "token_id": m.no_token_id or "",
                            "volume": m.volume_24h,
                        })

                    opp = HedgeOpportunity(
                        name=f"📦🔄 {event.title[:40]}", scanner="event_group",
                        hedge_type="group_arb", markets=markets_info,
                        total_cost=total_no, min_payout=1.0, max_payout=1.0,
                        guaranteed_profit=1.0 - total_no,
                        best_case_profit=1.0 - total_no,
                        net_profit_per_dollar=net_profit, confidence="GUARANTEED",
                    )
                    opportunities.append(opp)

        print(f"  [EventGroup] Scanned {len(events)} events ({markets_checked} markets) → {len(opportunities)} opportunities", flush=True)
        return opportunities, markets_checked


# =============================================================================
# SCANNER 2: THRESHOLD MISPRICING
# =============================================================================

class ThresholdScanner:
    """
    Scans crypto and stock price threshold markets for mispricings.
    """

    def __init__(self, gamma: GammaClient):
        self.gamma = gamma
        self._cache: dict[str, list[tuple[float, Market]]] = {}
        self._cache_time: float = 0

    def _parse_threshold(self, text: str, asset: str) -> float | None:
        import re
        t = text.lower()
        if asset.lower() not in t:
            return None

        patterns = [
            r"\$?([0-9]{1,3}(?:,[0-9]{3})+)(?:\s*(k|m))?",
            r"\$?([0-9]+(?:\.[0-9]+)?)(\s*[km])",
        ]

        for pat in patterns:
            for m in re.finditer(pat, t):
                raw = m.group(1).replace(",", "")
                suffix = (m.group(2) or "").strip()
                try:
                    val = float(raw)
                except Exception:
                    continue
                if suffix == "k":
                    val *= 1000
                elif suffix == "m":
                    val *= 1000000
                if val >= 1:
                    return val
        return None

    async def _fetch_asset_markets(self, asset: str) -> list[tuple[float, Market]]:
        config = THRESHOLD_ASSETS.get(asset, {})
        search_terms = config.get("search_terms", [])
        levels = config.get("levels", [])

        if not search_terms:
            return []

        found: dict[float, Market] = {}

        for term in search_terms:
            try:
                markets = await self.gamma.search_markets(term, limit=50)
                for m in markets:
                    if m.closed or m.resolved:
                        continue
                    q = m.question or ""
                    threshold = self._parse_threshold(q, asset)
                    if threshold:
                        if threshold not in found or m.volume_24h > found[threshold].volume_24h:
                            found[threshold] = m
            except Exception as e:
                print(f"    [Threshold] Error searching '{term}': {e}", flush=True)
                continue

        if len(found) < 2:
            try:
                trending = await self.gamma.get_trending_markets(limit=200)
                for m in trending:
                    if m.closed or m.resolved:
                        continue
                    q = m.question or ""
                    threshold = self._parse_threshold(q, asset)
                    if threshold:
                        if threshold not in found or m.volume_24h > found[threshold].volume_24h:
                            found[threshold] = m
            except Exception as e:
                print(f"    [Threshold] Error scanning trending for {asset}: {e}", flush=True)

        if levels:
            filtered: dict[float, Market] = {}
            for th, m in found.items():
                for lvl in levels:
                    if abs(th - lvl) / max(lvl, 1) < 0.05:
                        if th not in filtered or m.volume_24h > filtered[th].volume_24h:
                            filtered[th] = m
                        break
            found = filtered or found

        result = sorted(found.items(), key=lambda x: x[0])
        return result

    async def scan(self) -> tuple[list[HedgeOpportunity], int]:
        """Scan all assets for threshold mispricings. Returns (opportunities, markets_checked)."""
        opportunities = []
        total_markets = 0

        for asset, config in THRESHOLD_ASSETS.items():
            try:
                pairs = await self._fetch_asset_markets(asset)
                total_markets += len(pairs)

                if len(pairs) < 2:
                    continue

                for i in range(len(pairs)):
                    for j in range(i + 1, len(pairs)):
                        low_threshold, low_market = pairs[i]
                        high_threshold, high_market = pairs[j]

                        no_high = high_market.no_price
                        yes_low = low_market.yes_price
                        cost = no_high + yes_low

                        if cost <= 0 or cost >= 1.0:
                            continue

                        min_payout = 1.0
                        max_payout = 2.0
                        guaranteed_profit = min_payout - cost
                        best_profit = max_payout - cost
                        net_profit = guaranteed_profit / cost - POLY_FEE * 2

                        if net_profit > MIN_PROFIT_PER_DOLLAR:
                            opp = HedgeOpportunity(
                                name=f"📊 {asset} ${low_threshold:,} vs ${high_threshold:,}",
                                scanner="threshold", hedge_type="threshold",
                                markets=[
                                    {
                                        "id": high_market.id, "question": high_market.question,
                                        "position": "NO", "price": no_high,
                                        "token_id": high_market.no_token_id or "",
                                        "volume": high_market.volume_24h,
                                    },
                                    {
                                        "id": low_market.id, "question": low_market.question,
                                        "position": "YES", "price": yes_low,
                                        "token_id": low_market.yes_token_id,
                                        "volume": low_market.volume_24h,
                                    },
                                ],
                                total_cost=cost, min_payout=min_payout, max_payout=max_payout,
                                guaranteed_profit=guaranteed_profit,
                                best_case_profit=best_profit,
                                net_profit_per_dollar=net_profit, confidence="GUARANTEED",
                            )
                            opportunities.append(opp)

            except Exception as e:
                print(f"  [Threshold] Error scanning {asset}: {e}", flush=True)
                continue

        print(f"  [Threshold] Scanned {total_markets} markets across {len(THRESHOLD_ASSETS)} assets → {len(opportunities)} opportunities", flush=True)
        return opportunities, total_markets


# =============================================================================
# SCANNER 3: KNOWN PATTERN MONITOR
# =============================================================================

class KnownPatternScanner:
    """Monitor pre-researched hedge patterns."""

    def __init__(self, gamma: GammaClient):
        self.gamma = gamma
        self._patterns = list(KNOWN_PATTERNS)
        self._load_discovered()

    def _load_discovered(self):
        if PATTERNS_FILE.exists():
            try:
                with open(PATTERNS_FILE) as f:
                    saved = json.load(f)
                self._patterns.extend(saved)
                print(f"  [Known] Loaded {len(saved)} discovered patterns", flush=True)
            except Exception:
                pass

    def save_pattern(self, pattern: dict):
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        saved = []
        if PATTERNS_FILE.exists():
            try:
                with open(PATTERNS_FILE) as f:
                    saved = json.load(f)
            except Exception:
                pass
        saved.append(pattern)
        with open(PATTERNS_FILE, "w") as f:
            json.dump(saved, f, indent=2)

    async def _find_market(self, search: str) -> Market | None:
        try:
            markets = await self.gamma.search_markets(search, limit=5)
            return markets[0] if markets else None
        except Exception:
            return None

    async def scan(self) -> tuple[list[HedgeOpportunity], int]:
        """Check all known patterns. Returns (opportunities, patterns_checked)."""
        opportunities = []

        for pat in self._patterns:
            try:
                market_a = await self._find_market(pat["search_a"])
                market_b = await self._find_market(pat["search_b"])

                if not market_a or not market_b:
                    continue
                if market_a.closed or market_b.closed:
                    continue

                h_type = pat.get("hedge_type", "complementary")

                if h_type == "complementary":
                    cost = market_a.yes_price + market_b.yes_price
                    if cost > 0 and cost < 1.0:
                        net_p = (1.0 - cost) / cost - POLY_FEE * 2
                        if net_p > MIN_PROFIT_PER_DOLLAR:
                            opp = HedgeOpportunity(
                                name=f"🔗 {pat['name']}", scanner="known_pattern",
                                hedge_type=h_type,
                                markets=[
                                    {"id": market_a.id, "question": market_a.question,
                                     "position": "YES", "price": market_a.yes_price,
                                     "token_id": market_a.yes_token_id, "volume": market_a.volume_24h},
                                    {"id": market_b.id, "question": market_b.question,
                                     "position": "YES", "price": market_b.yes_price,
                                     "token_id": market_b.yes_token_id, "volume": market_b.volume_24h},
                                ],
                                total_cost=cost, min_payout=1.0, max_payout=1.0,
                                guaranteed_profit=1.0 - cost,
                                best_case_profit=1.0 - cost,
                                net_profit_per_dollar=net_p, confidence="GUARANTEED",
                            )
                            opportunities.append(opp)

                elif h_type == "exclusive":
                    cost = market_a.no_price + market_b.no_price
                    if cost > 0 and cost < 1.0:
                        net_p = (1.0 - cost) / cost - POLY_FEE * 2
                        if net_p > MIN_PROFIT_PER_DOLLAR:
                            opp = HedgeOpportunity(
                                name=f"❌ {pat['name']}", scanner="known_pattern",
                                hedge_type=h_type,
                                markets=[
                                    {"id": market_a.id, "question": market_a.question,
                                     "position": "NO", "price": market_a.no_price,
                                     "token_id": market_a.no_token_id or "", "volume": market_a.volume_24h},
                                    {"id": market_b.id, "question": market_b.question,
                                     "position": "NO", "price": market_b.no_price,
                                     "token_id": market_b.no_token_id or "", "volume": market_b.volume_24h},
                                ],
                                total_cost=cost, min_payout=1.0, max_payout=2.0,
                                guaranteed_profit=1.0 - cost,
                                best_case_profit=2.0 - cost,
                                net_profit_per_dollar=net_p, confidence="GUARANTEED",
                            )
                            opportunities.append(opp)

                elif h_type == "superset":
                    cost = market_b.yes_price + market_a.no_price
                    if cost > 0 and cost < 1.0:
                        net_p = (1.0 - cost) / cost - POLY_FEE * 2
                        if net_p > MIN_PROFIT_PER_DOLLAR:
                            opp = HedgeOpportunity(
                                name=f"⏰ {pat['name']}", scanner="known_pattern",
                                hedge_type=h_type,
                                markets=[
                                    {"id": market_b.id, "question": market_b.question,
                                     "position": "YES", "price": market_b.yes_price,
                                     "token_id": market_b.yes_token_id, "volume": market_b.volume_24h},
                                    {"id": market_a.id, "question": market_a.question,
                                     "position": "NO", "price": market_a.no_price,
                                     "token_id": market_a.no_token_id or "", "volume": market_a.volume_24h},
                                ],
                                total_cost=cost, min_payout=1.0, max_payout=2.0,
                                guaranteed_profit=1.0 - cost,
                                best_case_profit=2.0 - cost,
                                net_profit_per_dollar=net_p, confidence="GUARANTEED",
                            )
                            opportunities.append(opp)

            except Exception as e:
                print(f"  [Known] Error checking '{pat['name']}': {e}", flush=True)
                continue

        print(f"  [Known] Checked {len(self._patterns)} patterns → {len(opportunities)} opportunities", flush=True)
        return opportunities, len(self._patterns)


# =============================================================================
# HEDGE HISTORY TRACKER
# =============================================================================

class HedgeHistory:
    """Track discovered hedges and profit over time."""

    def __init__(self):
        self.discoveries: list[dict] = []
        self.total_guaranteed_profit = 0.0
        self.total_best_profit = 0.0
        self._load()

    def _load(self):
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        if HISTORY_FILE.exists():
            try:
                with open(HISTORY_FILE) as f:
                    data = json.load(f)
                self.discoveries = data.get("discoveries", [])
                self.total_guaranteed_profit = data.get("total_guaranteed_profit", 0)
                self.total_best_profit = data.get("total_best_profit", 0)
            except Exception:
                pass

    def _save(self):
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        with open(HISTORY_FILE, "w") as f:
            json.dump({
                "discoveries": self.discoveries[-100:],
                "total_guaranteed_profit": self.total_guaranteed_profit,
                "total_best_profit": self.total_best_profit,
            }, f, indent=2)

    def record(self, opp: HedgeOpportunity):
        self.discoveries.append({
            "name": opp.name, "scanner": opp.scanner, "type": opp.hedge_type,
            "cost": opp.total_cost, "profit": opp.guaranteed_profit,
            "best": opp.best_case_profit, "confidence": opp.confidence,
            "time": datetime.now(timezone.utc).isoformat(),
        })
        self.total_guaranteed_profit += opp.guaranteed_profit
        self.total_best_profit += opp.best_case_profit
        self._save()


# =============================================================================
# MAIN SERVER — FULL EXECUTION ENGINE
# =============================================================================

class HedgeServer:
    """Main server — orchestrates scanners + CLOB execution + risk management."""

    def __init__(self):
        self.tg = Telegram()
        self.gamma = GammaClient()
        self.history = HedgeHistory()
        self.db = HedgeDB(DB_FILE)
        self.risk = RiskManager()

        # CLOB Client (for live trading)
        self.clob: Optional[ClobClientWrapper] = None
        self.wallet: Optional[WalletManager] = None
        self._init_trading()

        # Scanners
        self.event_scanner = EventGroupScanner(self.gamma)
        self.threshold_scanner = ThresholdScanner(self.gamma)
        self.pattern_scanner = KnownPatternScanner(self.gamma)

        # State
        self.scan_count = 0
        self.total_opps_found = 0
        self.total_trades_executed = 0
        self.start_time = datetime.now(timezone.utc)
        self.last_summary = time.time()

        # Alert tracking
        self.alerted: dict[str, float] = {}

    def _init_trading(self):
        """Initialize CLOB client and wallet for live trading."""
        try:
            self.wallet = WalletManager()
            if self.wallet.is_unlocked:
                pk = self.wallet.get_unlocked_key()
                addr = self.wallet.address
                self.clob = ClobClientWrapper(private_key=pk, address=addr)
                print(f"  ✅ Wallet loaded: {addr}", flush=True)
                print(f"  ✅ CLOB client ready (EIP-712 auth)", flush=True)
            else:
                print("  ⚠️ No wallet configured — CLOB execution disabled", flush=True)
        except Exception as e:
            print(f"  ⚠️ Trading init failed: {e} — alerts only mode", flush=True)
            self.clob = None

    def _check_depth(self, token_id: str, buy_size_usd: float) -> tuple[bool, str]:
        """
        Check order book depth using VWAP before executing.
        Returns (ok, reason).
        """
        if not self.clob:
            return False, "no_clob_client"

        try:
            t0 = time.time()
            ob = self.clob.get_order_book(token_id)
            latency_ms = (time.time() - t0) * 1000
            self.risk.record_latency(latency_ms)

            # Parse order book
            asks_raw = ob.get("asks", [])
            bids_raw = ob.get("bids", [])

            asks = [(float(a.get("price", 0)), float(a.get("size", 0))) for a in asks_raw]
            bids = [(float(b.get("price", 0)), float(b.get("size", 0))) for b in bids_raw]

            if not asks:
                self.risk.record_thin_book(True)
                self.db.log_depth_check(token_id, 999.0, 0, 0, False, False)
                return False, "no_asks"

            # Check spread
            spread = best_spread(bids, asks)
            spread_ok = spread <= MAX_SPREAD

            # Check depth via VWAP
            # buy_size_usd is how much we want to buy in $ terms
            # For CLOB, size is in token units. At ask price p, $X buys X/p tokens
            best_ask_price = min(a[0] for a in asks if a[0] > 0)
            token_qty = buy_size_usd / best_ask_price if best_ask_price > 0 else 0

            cost, depth_ok = vwap_cost(asks, token_qty)

            # Total USD depth on ask side
            ask_depth_usd = sum(p * s for p, s in asks)
            depth_sufficient = ask_depth_usd >= MIN_DEPTH_USD and depth_ok

            self.risk.record_thin_book(not depth_sufficient)

            self.db.log_depth_check(
                token_id=token_id, spread=spread, ask_depth_usd=ask_depth_usd,
                vwap=cost, depth_ok=depth_sufficient, spread_ok=spread_ok,
            )

            if not spread_ok:
                return False, f"spread_too_wide ({spread:.4f})"
            if not depth_sufficient:
                return False, f"insufficient_depth (${ask_depth_usd:.2f} < ${MIN_DEPTH_USD})"

            return True, "ok"

        except Exception as e:
            self.risk.record_api_error()
            return False, f"depth_check_error: {e}"

    async def execute_hedge(self, opp: HedgeOpportunity) -> dict:
        """
        Execute a hedge opportunity via CLOB.
        Returns execution report dict.
        """
        report = {
            "executed": False,
            "legs": [],
            "total_spent": 0.0,
            "errors": [],
            "partial": False,
        }

        if not self.clob or not AUTO_TRADE:
            report["errors"].append("auto_trade_off_or_no_clob")
            return report

        # Kill switch check
        if self.risk.should_kill():
            reason = self.risk.kill_reason
            self.db.log_incident("kill_switch", f"Blocked trade: {opp.name}", reason)
            report["errors"].append(f"kill_switch: {reason}")
            await self.tg.send(
                f"⛔ <b>KILL SWITCH TRIGGERED</b>\n"
                f"Reason: {reason}\n"
                f"Blocked: {opp.name}\n"
                f"Trading suspended until restart."
            )
            return report

        # Exposure check
        trade_size = TRADE_BUDGET
        if not self.risk.can_take_trade(BANKROLL, trade_size):
            report["errors"].append(
                f"exposure_limit (current ${self.risk.current_open_exposure:.2f}, "
                f"max ${BANKROLL * self.risk.limits.max_open_exposure_pct:.2f})"
            )
            return report

        # Scale trade: how many units of the hedge to buy
        if opp.total_cost <= 0:
            report["errors"].append("invalid_cost")
            return report

        scale = trade_size / opp.total_cost
        legs_ok = 0

        for leg in opp.markets:
            token_id = leg.get("token_id", "")
            if not token_id:
                report["errors"].append(f"no_token_id for {leg['question'][:30]}")
                continue

            leg_amount_usd = leg["price"] * scale
            leg_size = leg_amount_usd / leg["price"] if leg["price"] > 0 else 0

            # VWAP depth check
            depth_ok, depth_reason = self._check_depth(token_id, leg_amount_usd)
            if not depth_ok:
                report["errors"].append(f"depth_fail ({leg['position']}): {depth_reason}")
                report["partial"] = True
                continue

            # Execute buy order via CLOB
            t0 = time.time()
            try:
                order_id, error = self.clob.buy_gtc(
                    token_id=token_id,
                    amount=round(leg_size, 2),
                    price=round(leg["price"], 2),
                )
                latency_ms = (time.time() - t0) * 1000
                self.risk.record_latency(latency_ms)

                if error:
                    self.risk.record_api_error()
                    self.db.log_order(
                        opp_name=opp.name, market_id=leg["id"], token_id=token_id,
                        side="BUY", price=leg["price"], size=leg_size,
                        status="error", error=error, latency_ms=latency_ms,
                    )
                    report["errors"].append(f"order_error ({leg['position']}): {error}")
                    report["partial"] = True
                else:
                    self.risk.record_trade()
                    self.db.log_order(
                        opp_name=opp.name, market_id=leg["id"], token_id=token_id,
                        side="BUY", price=leg["price"], size=leg_size,
                        order_id=order_id or "", status="submitted",
                        latency_ms=latency_ms,
                    )
                    report["legs"].append({
                        "market_id": leg["id"],
                        "position": leg["position"],
                        "price": leg["price"],
                        "size": leg_size,
                        "amount_usd": leg_amount_usd,
                        "order_id": order_id,
                    })
                    report["total_spent"] += leg_amount_usd
                    legs_ok += 1

            except Exception as e:
                self.risk.record_api_error()
                self.db.log_order(
                    opp_name=opp.name, market_id=leg["id"], token_id=token_id,
                    side="BUY", price=leg["price"], size=leg_size,
                    status="exception", error=str(e),
                )
                report["errors"].append(f"exception ({leg['position']}): {e}")
                report["partial"] = True

        # Assess result
        total_legs = len(opp.markets)
        if legs_ok == total_legs:
            report["executed"] = True
            self.risk.record_hedged_complete()
            self.risk.add_exposure(report["total_spent"])
            self.total_trades_executed += 1
            self.db.log_pnl(
                budget=trade_size, exposure=report["total_spent"],
                notes=f"Hedge executed: {opp.name}",
            )
        elif legs_ok > 0:
            report["partial"] = True
            self.risk.record_partial_fill()
            self.risk.add_exposure(report["total_spent"])
            self.db.log_incident(
                "partial_fill",
                f"{legs_ok}/{total_legs} legs filled for {opp.name}",
            )

        return report

    async def full_scan(self):
        """Run all scanners and collect opportunities."""
        self.scan_count += 1
        now_str = datetime.now(timezone.utc).strftime('%H:%M')
        print(f"\n{'='*60}", flush=True)
        print(f"[{now_str}] 🔍 Full Scan #{self.scan_count}", flush=True)
        print(f"{'='*60}", flush=True)

        # Kill switch check before scanning
        if self.risk.killed:
            print(f"  ⛔ KILLED — reason: {self.risk.kill_reason}. Scanning continues for alerts only.", flush=True)

        all_opps: list[HedgeOpportunity] = []
        total_markets_checked = 0

        # Run all scanners with timing
        for scanner_name, scanner in [
            ("event_group", self.event_scanner),
            ("threshold", self.threshold_scanner),
            ("known_pattern", self.pattern_scanner),
        ]:
            try:
                t0 = time.time()
                opps, markets = await scanner.scan()
                latency = (time.time() - t0) * 1000
                all_opps.extend(opps)
                total_markets_checked += markets

                self.db.log_scan(
                    scan_number=self.scan_count, scanner=scanner_name,
                    markets_checked=markets, opportunities_found=len(opps),
                    latency_ms=latency,
                )
            except Exception as e:
                self.db.log_scan(
                    scan_number=self.scan_count, scanner=scanner_name,
                    markets_checked=0, opportunities_found=0,
                    latency_ms=0, error=str(e),
                )
                print(f"  [!] {scanner_name} error: {e}", flush=True)

        # Sort by guaranteed profit
        all_opps.sort(key=lambda x: x.net_profit_per_dollar, reverse=True)

        if not all_opps:
            print(f"  ❌ No profitable hedges this scan", flush=True)
            if self.scan_count % 5 == 0:
                await self.tg.send(
                    f"🔍 Scan #{self.scan_count} [{now_str}] — "
                    f"No hedges found ({total_markets_checked} markets checked). "
                    f"Next scan in {SCAN_INTERVAL//60}m"
                )
            return

        self.total_opps_found += len(all_opps)
        print(f"\n  🎯 Found {len(all_opps)} profitable hedges!", flush=True)

        # Process and alert / execute each opportunity
        for opp in all_opps:
            key = opp.alert_key()
            opp.discovered_at = datetime.now(timezone.utc).isoformat()
            opp.last_price = opp.total_cost

            self.history.record(opp)
            self.db.log_opportunity(opp)

            # Check if we should alert
            should_alert = False
            if key not in self.alerted:
                should_alert = True
            else:
                old_profit = self.alerted[key]
                change = abs(opp.net_profit_per_dollar - old_profit) / max(abs(old_profit), 0.001)
                if change > REALERT_THRESHOLD:
                    should_alert = True

            # Attempt execution if AUTO_TRADE is on
            exec_report = None
            if AUTO_TRADE and self.clob and not self.risk.killed:
                exec_report = await self.execute_hedge(opp)
                if exec_report["executed"]:
                    self.db.log_opportunity(opp, executed=True)

            if should_alert:
                await self._send_alert(opp, exec_report)
                self.alerted[key] = opp.net_profit_per_dollar
                status = "EXECUTED" if (exec_report and exec_report["executed"]) else "ALERTED"
                print(f"  📢 {status}: {opp.name} | profit: ${opp.guaranteed_profit:+.4f}/unit", flush=True)
            else:
                print(f"  ✓ Known: {opp.name} | profit: ${opp.guaranteed_profit:+.4f}/unit", flush=True)

        # Clean expired alerts
        active_keys = {o.alert_key() for o in all_opps}
        expired = [k for k in self.alerted if k not in active_keys]
        for k in expired:
            del self.alerted[k]

    async def _send_alert(self, opp: HedgeOpportunity, exec_report: Optional[dict] = None):
        """Send detailed Telegram alert with execution results."""
        confidence_emoji = {
            "GUARANTEED": "🟢🟢🟢", "HIGH": "🟢🟢⚪", "MEDIUM": "🟡🟡⚪",
        }
        scanner_labels = {
            "event_group": "📦 Event Group Arb",
            "threshold": "📊 Threshold Hedge",
            "known_pattern": "🔗 Known Pattern",
        }

        msg = (
            f"{'='*25}\n"
            f"💰 <b>HEDGE FOUND: {opp.name}</b>\n"
            f"{'='*25}\n\n"
            f"🔍 Scanner: {scanner_labels.get(opp.scanner, opp.scanner)}\n"
            f"📋 Type: {opp.hedge_type}\n"
            f"🛡 Confidence: {confidence_emoji.get(opp.confidence, '⚪')} {opp.confidence}\n\n"
            f"<b>📊 LEGS:</b>\n"
        )

        for i, m in enumerate(opp.markets, 1):
            msg += (
                f"  Leg {i}: <b>{m['position']}</b> @ ${m['price']:.4f}\n"
                f"  └ {m['question'][:60]}\n"
                f"  └ Volume: ${m['volume']:,.0f}\n\n"
            )

        msg += (
            f"<b>💵 FINANCIALS:</b>\n"
            f"  Total cost: ${opp.total_cost:.4f}\n"
            f"  Min payout: ${opp.min_payout:.2f}\n"
            f"  Max payout: ${opp.max_payout:.2f}\n"
            f"  Guaranteed: ${opp.guaranteed_profit:+.4f}/unit\n"
            f"  Best case:  ${opp.best_case_profit:+.4f}/unit\n"
            f"  Net (after fees): ${opp.net_profit_per_dollar:+.4f}/$ \n\n"
        )

        # Trade instructions
        msg += f"<b>🛒 TRADE INSTRUCTIONS:</b>\n"
        for budget in [10, 25, 50, 100]:
            if opp.total_cost > 0:
                units = budget / opp.total_cost
                min_ret = units * opp.min_payout
                profit = min_ret - budget
                msg += f"\n  💵 ${budget} → min ${min_ret:.2f} (profit ${profit:+.2f})"

        # Execution results
        if exec_report:
            msg += "\n\n"
            if exec_report["executed"]:
                msg += (
                    f"🤖 <b>AUTO-EXECUTED ✅</b>\n"
                    f"  Spent: ${exec_report['total_spent']:.2f}\n"
                    f"  Legs filled: {len(exec_report['legs'])}/{len(opp.markets)}\n"
                )
                for leg in exec_report["legs"]:
                    msg += f"  ✅ {leg['position']} ${leg['amount_usd']:.2f} → order {leg['order_id'][:12]}...\n"
            elif exec_report["partial"]:
                msg += (
                    f"⚠️ <b>PARTIAL EXECUTION</b>\n"
                    f"  Legs filled: {len(exec_report['legs'])}/{len(opp.markets)}\n"
                )
                for err in exec_report["errors"]:
                    msg += f"  ❌ {err}\n"
            elif exec_report["errors"]:
                msg += f"❌ <b>EXECUTION FAILED</b>\n"
                for err in exec_report["errors"][:3]:
                    msg += f"  • {err}\n"
        elif not AUTO_TRADE:
            msg += f"\n\n⚠️ Auto-trade OFF — execute manually on polymarket.com"

        await self.tg.send(msg)

    async def send_summary(self):
        """Send periodic status summary with risk + DB stats."""
        uptime = datetime.now(timezone.utc) - self.start_time
        hours = uptime.total_seconds() / 3600
        active_count = len(self.alerted)
        db_stats = self.db.get_stats()

        msg = (
            f"📊 <b>STATUS REPORT — v4</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⏱ Uptime: {hours:.1f}h\n"
            f"🔍 Scans: {self.scan_count}\n"
            f"🎯 Opportunities: {self.total_opps_found}\n"
            f"🤖 Trades executed: {self.total_trades_executed}\n"
            f"📌 Active hedges: {active_count}\n\n"
            f"<b>📁 Database:</b>\n"
            f"  Scans logged: {db_stats['total_scans']}\n"
            f"  Opps logged: {db_stats['total_opps']}\n"
            f"  Orders filled: {db_stats['total_fills']}\n"
            f"  Order errors: {db_stats['total_errors']}\n"
            f"  Incidents: {db_stats['total_incidents']}\n\n"
            f"<b>⛔ Risk Manager:</b>\n"
            f"{self.risk.status_text()}\n\n"
        )

        if self.wallet and self.wallet.is_unlocked:
            try:
                bal = self.wallet.get_balances()
                msg += (
                    f"<b>💰 Wallet:</b>\n"
                    f"  USDC.e: ${bal.usdc_e:.2f}\n"
                    f"  POL: {bal.pol:.4f}\n\n"
                )
            except Exception:
                pass

        if self.alerted:
            msg += f"<b>Active Hedges:</b>\n"
            for key, profit in sorted(self.alerted.items(), key=lambda x: x[1], reverse=True)[:5]:
                msg += f"  • ${profit:+.4f}/$ — {key[:30]}\n"

        msg += (
            f"\n━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📈 History: {len(self.history.discoveries)} total discoveries\n"
            f"💰 Total guaranteed seen: ${self.history.total_guaranteed_profit:.4f}\n"
            f"⏭ Next scan in {SCAN_INTERVAL//60}m"
        )

        await self.tg.send(msg)
        self.last_summary = time.time()

    async def run(self):
        """Main loop."""
        print("=" * 60, flush=True)
        print("  🦞 PolyClaw Hedge Server v4 — Full Execution Engine", flush=True)
        print("  CLOB + Kill Switches + SQLite + VWAP", flush=True)
        print("=" * 60, flush=True)
        print(f"  📦 Event Group Scanner: 50 events/scan", flush=True)
        print(f"  📊 Threshold Scanner: {len(THRESHOLD_ASSETS)} assets, {sum(len(v['levels']) for v in THRESHOLD_ASSETS.values())} levels", flush=True)
        print(f"  🔗 Known Patterns: {len(KNOWN_PATTERNS)}", flush=True)
        print(f"  ⏱  Scan interval: {SCAN_INTERVAL}s", flush=True)
        print(f"  🤖 Auto-trade: {'ON' if AUTO_TRADE else 'OFF'}", flush=True)
        print(f"  💰 Budget: ${TRADE_BUDGET}/trade | Bankroll: ${BANKROLL}", flush=True)
        print(f"  🛡 Max spread: {MAX_SPREAD} | Min depth: ${MIN_DEPTH_USD}", flush=True)
        print(f"  ⛔ Kill switches: 7 active", flush=True)
        print(f"  📁 SQLite: {DB_FILE}", flush=True)
        if self.clob:
            print(f"  ✅ CLOB client: ready (EIP-712)", flush=True)
        else:
            print(f"  ⚠️ CLOB client: disabled (alerts only)", flush=True)
        print("=" * 60, flush=True)

        scanner_info = (
            f"📦 Event Groups: 50 events/scan\n"
            f"📊 Thresholds: {len(THRESHOLD_ASSETS)} assets, {sum(len(v['levels']) for v in THRESHOLD_ASSETS.values())} price levels\n"
            f"🔗 Known Patterns: {len(KNOWN_PATTERNS)}"
        )
        risk_info = (
            f"  • Partial fill streak: ≥{KILL_PARTIAL_FILL_STREAK} → kill\n"
            f"  • Partial fill /day: ≥{KILL_PARTIAL_FILL_DAY} → kill\n"
            f"  • API errors (10m): ≥{KILL_API_ERRORS_10M} → kill\n"
            f"  • Latency avg: ≥{KILL_LATENCY_MS}ms → kill\n"
            f"  • Thin book streak: ≥{KILL_THIN_BOOK_SCANS} → kill\n"
            f"  • Trades/hour: ≥{KILL_MAX_TRADES_PER_HOUR} → kill\n"
            f"  • Exposure: ≤{KILL_MAX_EXPOSURE_PCT*100:.0f}% of bankroll"
        )
        await self.tg.startup(scanner_info, risk_info)

        while True:
            try:
                await self.full_scan()

                if time.time() - self.last_summary >= SUMMARY_INTERVAL:
                    await self.send_summary()

            except Exception as e:
                err = traceback.format_exc()
                print(f"\n[ERROR] {e}\n{err}", flush=True)
                self.risk.record_api_error()
                self.db.log_incident("scan_error", str(e)[:500])
                try:
                    await self.tg.send(f"🚨 <b>ERROR</b>\n<code>{str(e)[:500]}</code>")
                except Exception:
                    pass

            print(f"\n  ⏳ Next scan in {SCAN_INTERVAL//60}m...", flush=True)
            await asyncio.sleep(SCAN_INTERVAL)


# =============================================================================
# ENTRY POINT
# =============================================================================

def main():
    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    STATE_DIR.mkdir(parents=True, exist_ok=True)

    server = HedgeServer()
    try:
        asyncio.run(server.run())
    except KeyboardInterrupt:
        print("\n[EXIT] Server stopped.", flush=True)
    except Exception as e:
        print(f"\n[FATAL] {e}", flush=True)
        traceback.print_exc()


if __name__ == "__main__":
    main()

# Auto-deploy test 2026-02-14 23:09
