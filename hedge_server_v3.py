#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║          🦞 PolyClaw Hedge Server v3 — The Money Machine         ║
║          3 Scanners + Smart Alerts + Auto-Discovery              ║
╚══════════════════════════════════════════════════════════════════════╝

SCANNERS (all price-based, NO AI needed):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. EVENT GROUP ARBITRAGE
   - Fetches event groups (multi-market events)
   - If sum of YES prices < $1 → buy all YES → guaranteed profit
   - Example: Election with 3 candidates priced 0.30+0.35+0.25 = $0.90 → profit $0.10

2. THRESHOLD MISPRICING SCANNER
   - Scans crypto (BTC, ETH, SOL, XRP) & stocks (AAPL, META, PLTR, GOOGL)
   - Finds mispricings where lower threshold priced wrong vs higher
   - If NO(high) + YES(low) < $1 → guaranteed $1 payout minimum

3. KNOWN PATTERN MONITOR (from AI discovery)
   - Pre-researched hedge pairs checked every scan
   - Correct coverage calculations per hedge type
   - Saves newly discovered patterns to JSON

ALERTS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Every profitable hedge → instant Telegram with exact trade instructions
- Re-alerts when profit changes by >5%
- 2-hour summary with portfolio overview
"""

import os
import sys
import json
import time
import asyncio
import platform
import traceback
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, field

import httpx

# PolyClaw imports
sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from lib.gamma_client import GammaClient, Market, MarketGroup


# =============================================================================
# CONFIGURATION
# =============================================================================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8331165268:AAEA84wTDNeFuPhRJkjLiUqxxkaPEuL2B-o")
TELEGRAM_CHAT_IDS = json.loads(os.getenv("TELEGRAM_CHAT_IDS", '["1688623770","1675476723","-5264145102"]'))

SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL", "180"))  # 3 min between scans
SUMMARY_INTERVAL = int(os.getenv("SUMMARY_INTERVAL", "7200"))  # 2hr

# Event group safety filters
MIN_EVENT_VOLUME_24H = float(os.getenv("MIN_EVENT_VOLUME_24H", "5000"))

# Trading
MIN_PROFIT_PER_DOLLAR = float(os.getenv("MIN_PROFIT", "0.003"))  # $0.003 min profit per $1
AUTO_TRADE = os.getenv("AUTO_TRADE", "false").lower() == "true"
TRADE_BUDGET = float(os.getenv("TRADE_BUDGET", "50"))  # $ per trade

# Fee on Polymarket (approximately)
POLY_FEE = 0.02  # ~2% estimated fee per side

# Re-alert threshold (profit change %)
REALERT_THRESHOLD = 0.05

# State files
STATE_DIR = Path(__file__).parent / "data"
PATTERNS_FILE = STATE_DIR / "discovered_patterns.json"
HISTORY_FILE = STATE_DIR / "hedge_history.json"


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
    # Fed Interest Rates (complementary - one must be true)
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
    # Trump Nominations (exclusive)
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
    # Iran Strikes (superset — shorter deadline ⊂ longer deadline)
    {
        "name": "Iran Strike Timeframe",
        "search_a": "strikes Iran by February",
        "search_b": "strikes Iran by March",
        "hedge_type": "superset",  # Feb < March, if Feb=YES then March=YES
        "desc": "Strike by Feb → Strike by March too. Hedge: YES(March) + NO(Feb).",
    },
]


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

    async def startup(self, scanner_info: str):
        now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
        await self.send(
            "🦞 <b>PolyClaw Hedge Server v3 ONLINE</b>\n\n"
            f"⏰ {now}\n"
            f"🔄 Scan every: {SCAN_INTERVAL//60} min\n"
            f"🤖 Auto-trade: {'ON ✅' if AUTO_TRADE else 'OFF (alerts only)'}\n"
            f"💰 Budget: ${TRADE_BUDGET:.0f} per trade\n"
            f"📊 Fee estimate: {POLY_FEE*100:.0f}%\n\n"
            f"{scanner_info}\n"
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
        net_after_fees = net_profit - (budget * POLY_FEE * 2)  # buy + sell fees

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
        """Heuristic check for truly exclusive outcomes (winner/nominee/etc)."""
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
        # Exclusive groups typically sum close to 1.0 (overround allowed)
        if total_yes < 0.8 or total_yes > 1.2:
            return False

        return True

    async def scan(self) -> list[HedgeOpportunity]:
        """Scan event groups for arbitrage."""
        opportunities = []

        try:
            events = await self.gamma.get_events(limit=50)
        except Exception as e:
            print(f"  [EventGroup] Error fetching events: {e}", flush=True)
            return []

        for event in events:
            active_markets = [m for m in event.markets if m.active and not m.closed and not m.resolved]

            if len(active_markets) < 2:
                continue

            if not self._is_exclusive_event(event, active_markets):
                continue

            total_volume = sum(m.volume_24h for m in active_markets)
            if total_volume < MIN_EVENT_VOLUME_24H:
                continue

            # Use group arb only for 3+ outcomes to avoid ambiguous two-market sets
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
                            "id": m.id,
                            "question": m.question,
                            "position": "YES",
                            "price": m.yes_price,
                            "token_id": m.yes_token_id,
                            "volume": m.volume_24h,
                        })

                    opp = HedgeOpportunity(
                        name=f"📦 {event.title[:40]}",
                        scanner="event_group",
                        hedge_type="group_arb",
                        markets=markets_info,
                        total_cost=total_yes,
                        min_payout=1.0,
                        max_payout=1.0,
                        guaranteed_profit=1.0 - total_yes,
                        best_case_profit=1.0 - total_yes,
                        net_profit_per_dollar=net_profit,
                        confidence="GUARANTEED",
                    )
                    opportunities.append(opp)

            # Strategy 2: Sum of NO prices < 1 (rare but possible)
            total_no = sum(m.no_price for m in active_markets)
            if total_no > 0 and total_no < (1.0 - MIN_PROFIT_PER_DOLLAR - POLY_FEE * 2):
                profit_per_dollar = (1.0 - total_no) / total_no
                net_profit = profit_per_dollar - POLY_FEE * 2

                if net_profit > MIN_PROFIT_PER_DOLLAR:
                    markets_info = []
                    for m in active_markets:
                        markets_info.append({
                            "id": m.id,
                            "question": m.question,
                            "position": "NO",
                            "price": m.no_price,
                            "token_id": m.no_token_id or "",
                            "volume": m.volume_24h,
                        })

                    opp = HedgeOpportunity(
                        name=f"📦🔄 {event.title[:40]}",
                        scanner="event_group",
                        hedge_type="group_arb",
                        markets=markets_info,
                        total_cost=total_no,
                        min_payout=1.0,
                        max_payout=1.0,
                        guaranteed_profit=1.0 - total_no,
                        best_case_profit=1.0 - total_no,
                        net_profit_per_dollar=net_profit,
                        confidence="GUARANTEED",
                    )
                    opportunities.append(opp)

            # Note: two-market Y/N arb disabled for safety

        print(f"  [EventGroup] Scanned {len(events)} events → {len(opportunities)} opportunities", flush=True)
        return opportunities


# =============================================================================
# SCANNER 2: THRESHOLD MISPRICING
# =============================================================================

class ThresholdScanner:
    """
    Scans crypto and stock price threshold markets for mispricings.

    For thresholds: "BTC > $72K" and "BTC > $68K"
    - If BTC > 72K, then BTC > 68K is guaranteed
    - Hedge: Buy NO(72K) + YES(68K)
    - Scenarios:
      BTC > 72K  → NO loses($0) + YES wins($1) = $1
      68K<BTC<72K → NO wins($1) + YES wins($1) = $2 ← BONUS
      BTC < 68K  → NO wins($1) + YES loses($0) = $1
    - Min payout: $1. 
    - If cost < $1 → GUARANTEED PROFIT
    """

    def __init__(self, gamma: GammaClient):
        self.gamma = gamma
        self._cache: dict[str, list[tuple[float, Market]]] = {}
        self._cache_time: float = 0

    def _parse_threshold(self, text: str, asset: str) -> float | None:
        """Extract a numeric threshold from a market question."""
        import re

        t = text.lower()
        if asset.lower() not in t:
            return None

        # Common forms: $72,000 | 72k | 72,000 | 72 K | 1.5m
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
        """Find all price threshold markets for an asset, return (threshold, market) pairs."""
        config = THRESHOLD_ASSETS.get(asset, {})
        search_terms = config.get("search_terms", [])
        levels = config.get("levels", [])

        if not search_terms:
            return []

        found: dict[float, Market] = {}  # threshold → market

        # 1) Direct search with specific terms
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

        # 2) Fallback: scan trending markets and filter by asset name
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

        # Prefer thresholds close to known levels to reduce noise
        if levels:
            filtered: dict[float, Market] = {}
            for th, m in found.items():
                for lvl in levels:
                    if abs(th - lvl) / max(lvl, 1) < 0.05:
                        if th not in filtered or m.volume_24h > filtered[th].volume_24h:
                            filtered[th] = m
                        break
            found = filtered or found

        # Sort by threshold level
        result = sorted(found.items(), key=lambda x: x[0])
        return result

    async def scan(self) -> list[HedgeOpportunity]:
        """Scan all assets for threshold mispricings."""
        opportunities = []
        total_markets = 0

        for asset, config in THRESHOLD_ASSETS.items():
            try:
                pairs = await self._fetch_asset_markets(asset)
                total_markets += len(pairs)

                if len(pairs) < 2:
                    continue

                # Check all consecutive threshold pairs
                for i in range(len(pairs)):
                    for j in range(i + 1, len(pairs)):
                        low_threshold, low_market = pairs[i]
                        high_threshold, high_market = pairs[j]

                        # Hedge: NO(high) + YES(low)
                        no_high = high_market.no_price  # NO on "above $72K"
                        yes_low = low_market.yes_price   # YES on "above $68K"
                        cost = no_high + yes_low

                        if cost <= 0 or cost >= 1.0:
                            continue

                        # All scenarios pay at least $1
                        # Middle scenario (between thresholds) pays $2
                        min_payout = 1.0
                        max_payout = 2.0  # If price between the two thresholds

                        guaranteed_profit = min_payout - cost
                        best_profit = max_payout - cost
                        net_profit = guaranteed_profit / cost - POLY_FEE * 2

                        if net_profit > MIN_PROFIT_PER_DOLLAR:
                            opp = HedgeOpportunity(
                                name=f"📊 {asset} ${low_threshold:,} vs ${high_threshold:,}",
                                scanner="threshold",
                                hedge_type="threshold",
                                markets=[
                                    {
                                        "id": high_market.id,
                                        "question": high_market.question,
                                        "position": "NO",
                                        "price": no_high,
                                        "token_id": high_market.no_token_id or "",
                                        "volume": high_market.volume_24h,
                                    },
                                    {
                                        "id": low_market.id,
                                        "question": low_market.question,
                                        "position": "YES",
                                        "price": yes_low,
                                        "token_id": low_market.yes_token_id,
                                        "volume": low_market.volume_24h,
                                    },
                                ],
                                total_cost=cost,
                                min_payout=min_payout,
                                max_payout=max_payout,
                                guaranteed_profit=guaranteed_profit,
                                best_case_profit=best_profit,
                                net_profit_per_dollar=net_profit,
                                confidence="GUARANTEED",
                            )
                            opportunities.append(opp)

                        # Also check reverse: YES(high) + NO(low)
                        # This is NOT guaranteed but might have value
                        yes_high = high_market.yes_price
                        no_low = low_market.no_price
                        cost_rev = yes_high + no_low

                        if cost_rev > 0 and cost_rev < 1.0:
                            # BTC > 72K: YES wins + NO loses = $1
                            # 68K < BTC < 72K: YES loses + NO loses = $0 (LOSS!)
                            # BTC < 68K: YES loses + NO wins = $1
                            # NOT guaranteed — only wins in 2/3 scenarios
                            # Still interesting if probability of middle is very low
                            pass  # Skip non-guaranteed for safety

            except Exception as e:
                print(f"  [Threshold] Error scanning {asset}: {e}", flush=True)
                continue

        print(f"  [Threshold] Scanned {total_markets} markets across {len(THRESHOLD_ASSETS)} assets → {len(opportunities)} opportunities", flush=True)
        return opportunities


# =============================================================================
# SCANNER 3: KNOWN PATTERN MONITOR
# =============================================================================

class KnownPatternScanner:
    """Monitor pre-researched hedge patterns."""

    def __init__(self, gamma: GammaClient):
        self.gamma = gamma
        self._patterns = list(KNOWN_PATTERNS)
        # Load any discovered patterns
        self._load_discovered()

    def _load_discovered(self):
        """Load previously discovered patterns from disk."""
        if PATTERNS_FILE.exists():
            try:
                with open(PATTERNS_FILE) as f:
                    saved = json.load(f)
                self._patterns.extend(saved)
                print(f"  [Known] Loaded {len(saved)} discovered patterns", flush=True)
            except Exception:
                pass

    def save_pattern(self, pattern: dict):
        """Save a new pattern to disk."""
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

    async def scan(self) -> list[HedgeOpportunity]:
        """Check all known patterns."""
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
                    # Both can't be YES at same time; buying YES on both
                    # If they truly complement (A or B must be true):
                    # Cost = yes_a + yes_b, Payout = $1
                    cost = market_a.yes_price + market_b.yes_price
                    if cost > 0 and cost < 1.0:
                        net_p = (1.0 - cost) / cost - POLY_FEE * 2
                        if net_p > MIN_PROFIT_PER_DOLLAR:
                            opp = HedgeOpportunity(
                                name=f"🔗 {pat['name']}",
                                scanner="known_pattern",
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
                                net_profit_per_dollar=net_p,
                                confidence="GUARANTEED",
                            )
                            opportunities.append(opp)

                elif h_type == "exclusive":
                    # A and B are mutually exclusive (both can't be YES)
                    # Buy NO on both: if at most ONE is YES, at least one NO wins
                    # Cost = no_a + no_b. If both can't be YES, worst case one is YES
                    # Payout: at least $1 (the loser's NO wins)
                    cost = market_a.no_price + market_b.no_price
                    if cost > 0 and cost < 1.0:
                        net_p = (1.0 - cost) / cost - POLY_FEE * 2
                        if net_p > MIN_PROFIT_PER_DOLLAR:
                            opp = HedgeOpportunity(
                                name=f"❌ {pat['name']}",
                                scanner="known_pattern",
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
                                net_profit_per_dollar=net_p,
                                confidence="GUARANTEED",
                            )
                            opportunities.append(opp)

                elif h_type == "superset":
                    # A is shorter deadline than B (A=YES → B=YES)
                    # Hedge: YES(B) + NO(A) — always pays $1 minimum
                    cost = market_b.yes_price + market_a.no_price
                    if cost > 0 and cost < 1.0:
                        net_p = (1.0 - cost) / cost - POLY_FEE * 2
                        if net_p > MIN_PROFIT_PER_DOLLAR:
                            opp = HedgeOpportunity(
                                name=f"⏰ {pat['name']}",
                                scanner="known_pattern",
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
                                net_profit_per_dollar=net_p,
                                confidence="GUARANTEED",
                            )
                            opportunities.append(opp)

            except Exception as e:
                print(f"  [Known] Error checking '{pat['name']}': {e}", flush=True)
                continue

        print(f"  [Known] Checked {len(self._patterns)} patterns → {len(opportunities)} opportunities", flush=True)
        return opportunities


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
                "discoveries": self.discoveries[-100:],  # Keep last 100
                "total_guaranteed_profit": self.total_guaranteed_profit,
                "total_best_profit": self.total_best_profit,
            }, f, indent=2)

    def record(self, opp: HedgeOpportunity):
        self.discoveries.append({
            "name": opp.name,
            "scanner": opp.scanner,
            "type": opp.hedge_type,
            "cost": opp.total_cost,
            "profit": opp.guaranteed_profit,
            "best": opp.best_case_profit,
            "confidence": opp.confidence,
            "time": datetime.now(timezone.utc).isoformat(),
        })
        self.total_guaranteed_profit += opp.guaranteed_profit
        self.total_best_profit += opp.best_case_profit
        self._save()


# =============================================================================
# MAIN SERVER
# =============================================================================

class HedgeServer:
    """Main server — orchestrates all scanners."""

    def __init__(self):
        self.tg = Telegram()
        self.gamma = GammaClient()
        self.history = HedgeHistory()

        # Scanners
        self.event_scanner = EventGroupScanner(self.gamma)
        self.threshold_scanner = ThresholdScanner(self.gamma)
        self.pattern_scanner = KnownPatternScanner(self.gamma)

        # State
        self.scan_count = 0
        self.total_opps_found = 0
        self.start_time = datetime.now(timezone.utc)
        self.last_summary = time.time()

        # Alert tracking (for smart re-alerting)
        self.alerted: dict[str, float] = {}  # key → last profit alerted

    async def full_scan(self):
        """Run all scanners and collect opportunities."""
        self.scan_count += 1
        now_str = datetime.now(timezone.utc).strftime('%H:%M')
        print(f"\n{'='*60}", flush=True)
        print(f"[{now_str}] 🔍 Full Scan #{self.scan_count}", flush=True)
        print(f"{'='*60}", flush=True)

        all_opps: list[HedgeOpportunity] = []

        # Run all scanners
        try:
            event_opps = await self.event_scanner.scan()
            all_opps.extend(event_opps)
        except Exception as e:
            print(f"  [!] Event scanner error: {e}", flush=True)

        try:
            threshold_opps = await self.threshold_scanner.scan()
            all_opps.extend(threshold_opps)
        except Exception as e:
            print(f"  [!] Threshold scanner error: {e}", flush=True)

        try:
            pattern_opps = await self.pattern_scanner.scan()
            all_opps.extend(pattern_opps)
        except Exception as e:
            print(f"  [!] Pattern scanner error: {e}", flush=True)

        # Sort by guaranteed profit
        all_opps.sort(key=lambda x: x.net_profit_per_dollar, reverse=True)

        if not all_opps:
            print(f"  ❌ No profitable hedges this scan", flush=True)
            if self.scan_count % 5 == 0:
                await self.tg.send(
                    f"🔍 Scan #{self.scan_count} [{now_str}] — "
                    f"No hedges found. Scanning 3 strategies across "
                    f"{len(THRESHOLD_ASSETS)} assets + {len(KNOWN_PATTERNS)} patterns. "
                    f"Next scan in {SCAN_INTERVAL//60}m"
                )
            return

        self.total_opps_found += len(all_opps)
        print(f"\n  🎯 Found {len(all_opps)} profitable hedges!", flush=True)

        # Process and alert
        for opp in all_opps:
            key = opp.alert_key()
            opp.discovered_at = datetime.now(timezone.utc).isoformat()
            opp.last_price = opp.total_cost

            # Record in history
            self.history.record(opp)

            # Check if we should alert (new or significant price change)
            should_alert = False
            if key not in self.alerted:
                should_alert = True  # New discovery
            else:
                old_profit = self.alerted[key]
                change = abs(opp.net_profit_per_dollar - old_profit) / max(abs(old_profit), 0.001)
                if change > REALERT_THRESHOLD:
                    should_alert = True  # Significant change

            if should_alert:
                await self._send_alert(opp)
                self.alerted[key] = opp.net_profit_per_dollar
                print(f"  📢 ALERTED: {opp.name} | profit: ${opp.guaranteed_profit:+.4f}/unit", flush=True)
            else:
                print(f"  ✓ Known: {opp.name} | profit: ${opp.guaranteed_profit:+.4f}/unit", flush=True)

        # Clean expired alerts
        active_keys = {o.alert_key() for o in all_opps}
        expired = [k for k in self.alerted if k not in active_keys]
        for k in expired:
            del self.alerted[k]

    async def _send_alert(self, opp: HedgeOpportunity):
        """Send detailed Telegram alert for a hedge opportunity."""
        confidence_emoji = {
            "GUARANTEED": "🟢🟢🟢",
            "HIGH": "🟢🟢⚪",
            "MEDIUM": "🟡🟡⚪",
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

        # Trade instructions for different budgets
        msg += f"<b>🛒 TRADE INSTRUCTIONS:</b>\n"
        for budget in [10, 25, 50, 100]:
            if opp.total_cost > 0:
                units = budget / opp.total_cost
                min_ret = units * opp.min_payout
                max_ret = units * opp.max_payout
                profit = min_ret - budget
                msg += f"\n  💵 ${budget} → min ${min_ret:.2f} (profit ${profit:+.2f})"
                if opp.max_payout > opp.min_payout:
                    msg += f" | max ${max_ret:.2f}"

        if not AUTO_TRADE:
            msg += f"\n\n⚠️ Auto-trade OFF — execute manually on polymarket.com"
        else:
            msg += f"\n\n🤖 Auto-executing ${TRADE_BUDGET:.0f}..."

        await self.tg.send(msg)

    async def send_summary(self):
        """Send periodic status summary."""
        uptime = datetime.now(timezone.utc) - self.start_time
        hours = uptime.total_seconds() / 3600

        active_count = len(self.alerted)

        msg = (
            f"📊 <b>STATUS REPORT — v3</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⏱ Uptime: {hours:.1f}h\n"
            f"🔍 Scans completed: {self.scan_count}\n"
            f"🎯 Total opportunities: {self.total_opps_found}\n"
            f"📌 Active hedges now: {active_count}\n\n"
            f"<b>Scanners:</b>\n"
            f"  📦 Event Groups: 50 events/scan\n"
            f"  📊 Threshold: {sum(len(v['levels']) for v in THRESHOLD_ASSETS.values())} price levels\n"
            f"  🔗 Known Patterns: {len(KNOWN_PATTERNS)}\n\n"
        )

        if self.alerted:
            msg += f"<b>Active Hedges:</b>\n"
            for key, profit in sorted(self.alerted.items(), key=lambda x: x[1], reverse=True)[:5]:
                msg += f"  • ${profit:+.4f}/$ — {key[:30]}\n"

        msg += (
            f"\n━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📈 History: {len(self.history.discoveries)} total discoveries\n"
            f"💰 Total guaranteed profit seen: ${self.history.total_guaranteed_profit:.4f}\n"
            f"⏭ Next scan in {SCAN_INTERVAL//60}m"
        )

        await self.tg.send(msg)
        self.last_summary = time.time()

    async def run(self):
        """Main loop."""
        print("=" * 60, flush=True)
        print("  🦞 PolyClaw Hedge Server v3 — The Money Machine", flush=True)
        print("  3 Scanners | Smart Alerts | Auto-Discovery", flush=True)
        print("=" * 60, flush=True)
        print(f"  📦 Event Group Scanner: 50 events per scan", flush=True)
        print(f"  📊 Threshold Scanner: {len(THRESHOLD_ASSETS)} assets, {sum(len(v['levels']) for v in THRESHOLD_ASSETS.values())} levels", flush=True)
        print(f"  🔗 Known Patterns: {len(KNOWN_PATTERNS)}", flush=True)
        print(f"  ⏱  Scan interval: {SCAN_INTERVAL}s", flush=True)
        print(f"  🤖 Auto-trade: {'ON' if AUTO_TRADE else 'OFF'}", flush=True)
        print("=" * 60, flush=True)

        scanner_info = (
            f"📦 Event Groups: 50 events/scan\n"
            f"📊 Thresholds: {len(THRESHOLD_ASSETS)} assets, {sum(len(v['levels']) for v in THRESHOLD_ASSETS.values())} price levels\n"
            f"🔗 Known Patterns: {len(KNOWN_PATTERNS)}"
        )
        await self.tg.startup(scanner_info)

        while True:
            try:
                await self.full_scan()

                # Summary every 2 hours
                if time.time() - self.last_summary >= SUMMARY_INTERVAL:
                    await self.send_summary()

            except Exception as e:
                err = traceback.format_exc()
                print(f"\n[ERROR] {e}\n{err}", flush=True)
                try:
                    await self.tg.send(f"🚨 <b>ERROR</b>\n<code>{str(e)[:500]}</code>")
                except Exception:
                    pass

            # Wait for next scan
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
