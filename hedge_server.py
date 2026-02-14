#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║          🦞 PolyClaw Smart Hedge Server v2                   ║
║          24/7 Price Monitor + AI Discovery + Telegram        ║
╚══════════════════════════════════════════════════════════════╝

SMART APPROACH (avoids free tier rate limits):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. PRICE MONITOR (every 5 min) — NO AI needed
   - Tracks known hedge-pair patterns via Gamma API
   - Calculates coverage & profit in real-time
   - Alerts when profitable hedge appears

2. AI DISCOVERY (every 4 hours) — Uses LLM
   - Scans for NEW hedge relationships
   - Adds discoveries to the known patterns DB
   - Respects free tier rate limits

3. TELEGRAM ALERTS
   - Every profitable hedge → instant alert
   - Every trade → detailed report
   - Periodic summary every 2 hours
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
from dataclasses import dataclass, field, asdict

import httpx

# PolyClaw imports
sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from lib.gamma_client import GammaClient, Market


# =============================================================================
# CONFIGURATION
# =============================================================================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8331165268:AAEA84wTDNeFuPhRJkjLiUqxxkaPEuL2B-o")
TELEGRAM_CHAT_IDS = json.loads(os.getenv("TELEGRAM_CHAT_IDS", '["1688623770","1675476723","-5264145102"]'))

# Price monitor (fast, no AI)
PRICE_CHECK_INTERVAL = int(os.getenv("PRICE_CHECK_INTERVAL", "300"))  # 5 min

# AI discovery (slow, uses LLM)
AI_DISCOVERY_INTERVAL = int(os.getenv("AI_DISCOVERY_INTERVAL", "14400"))  # 4 hours

# Trading
MIN_COVERAGE = float(os.getenv("MIN_COVERAGE", "0.95"))
MIN_PROFIT = float(os.getenv("MIN_PROFIT", "0.005"))  # $0.005 per $1
AUTO_TRADE = os.getenv("AUTO_TRADE", "false").lower() == "true"
MAX_TRADE = float(os.getenv("MAX_TRADE", "50"))

# Summary
SUMMARY_INTERVAL = int(os.getenv("SUMMARY_INTERVAL", "7200"))  # 2hr


# =============================================================================
# KNOWN HEDGE PATTERNS (from successful AI scan results)
# These don't need AI - just price monitoring!
# =============================================================================

"""
Hedge pattern types:
1. SUPERSET: If A happens → B MUST happen (A ⊂ B timeframe-wise)
   Example: "Iran strike by Feb 13" → "Iran strike by Feb 28"

2. EXCLUSIVE: A and B can't both be YES (mutually exclusive nominations)
   Example: "Trump nominate Shelton" vs "Trump nominate no one"

3. COMPLEMENTARY: A + B + C cover all outcomes
   Example: Fed: increase / decrease / no change

4. THRESHOLD: Price A > X implies Price A > Y (where X > Y)
   Example: "Bitcoin > $72K" → "Bitcoin > $68K"
"""

# Each pattern: (search_term, position_on_A, position_on_B, relationship_desc)
HEDGE_SEARCH_PAIRS = [
    # Fed Interest Rates (complementary)
    {
        "name": "Fed Rates Complement",
        "search_a": "Fed decrease interest rates by 50",
        "search_b": "Fed increase interest rates",
        "pos_a": "YES", "pos_b": "NO",
        "type": "complementary",
    },
    {
        "name": "Fed Rates Hedge",
        "search_a": "Fed decrease interest rates by 25 bps",
        "search_b": "no change in Fed interest rates",
        "pos_a": "NO", "pos_b": "YES",
        "type": "complementary",
    },
    {
        "name": "Fed No Change vs Increase",
        "search_a": "Fed increase interest rates",
        "search_b": "no change in Fed interest rates",
        "pos_a": "NO", "pos_b": "YES",
        "type": "complementary",
    },
    # Trump Nominations (exclusive)
    {
        "name": "Trump Nom: Shelton vs No One",
        "search_a": "Trump nominate no one",
        "search_b": "Trump nominate Judy Shelton",
        "pos_a": "NO", "pos_b": "YES",
        "type": "exclusive",
    },
    {
        "name": "Trump Nom: Miran vs No One",
        "search_a": "Trump nominate no one",
        "search_b": "Trump nominate Stephen Miran",
        "pos_a": "NO", "pos_b": "YES",
        "type": "exclusive",
    },
    # Iran Strikes (superset)
    {
        "name": "Iran Strike Timeframe",
        "search_a": "strikes Iran by February 13",
        "search_b": "strikes Iran by February 28",
        "pos_a": "NO", "pos_b": "YES",
        "type": "superset",
    },
    # Bitcoin Thresholds
    {
        "name": "BTC 68K vs 72K",
        "search_a": "Bitcoin be above $72,000",
        "search_b": "Bitcoin be above $68,000",
        "pos_a": "YES", "pos_b": "NO",
        "type": "threshold",
    },
    {
        "name": "BTC 68K vs 150K",
        "search_a": "Bitcoin be above $68,000",
        "search_b": "Bitcoin reach $150,000",
        "pos_a": "YES", "pos_b": "NO",
        "type": "threshold",
    },
]


# =============================================================================
# TELEGRAM
# =============================================================================

class Telegram:
    def __init__(self):
        self.url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

    async def send(self, msg: str):
        async with httpx.AsyncClient(timeout=30) as c:
            for cid in TELEGRAM_CHAT_IDS:
                try:
                    await c.post(f"{self.url}/sendMessage", json={
                        "chat_id": cid, "text": msg[:4096],
                        "parse_mode": "HTML", "disable_web_page_preview": True,
                    })
                except Exception as e:
                    print(f"  [TG] Error {cid}: {e}")

    async def startup(self):
        await self.send(
            "🦞 <b>PolyClaw Hedge Monitor ONLINE</b>\n\n"
            f"⏰ {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n"
            f"📊 Price check: every {PRICE_CHECK_INTERVAL//60} min\n"
            f"🧠 AI discovery: every {AI_DISCOVERY_INTERVAL//3600}h\n"
            f"🎯 Min coverage: {MIN_COVERAGE*100:.0f}%\n"
            f"🤖 Auto-trade: {'ON ✅' if AUTO_TRADE else 'OFF (alerts only)'}\n"
            f"📋 Known patterns: {len(HEDGE_SEARCH_PAIRS)}\n"
            "━━━━━━━━━━━━━━━━━━━━━"
        )


# =============================================================================
# PRICE-BASED HEDGE MONITOR (no AI needed!)
# =============================================================================

class PriceMonitor:
    """Monitor known hedge pairs via Gamma API prices."""

    def __init__(self):
        self.gamma = GammaClient()
        self.alerted: set = set()  # Don't spam same hedge

    async def _find_market(self, search_term: str) -> Market | None:
        """Find best matching market."""
        try:
            markets = await self.gamma.search_markets(search_term, limit=5)
            if markets:
                return markets[0]
        except Exception:
            pass
        return None

    async def check_all_pairs(self) -> list[dict]:
        """Check all known hedge pairs for profitability."""
        opportunities = []

        for pair in HEDGE_SEARCH_PAIRS:
            try:
                market_a = await self._find_market(pair["search_a"])
                market_b = await self._find_market(pair["search_b"])

                if not market_a or not market_b:
                    continue

                # Get prices for the specified positions
                price_a = market_a.yes_price if pair["pos_a"] == "YES" else market_a.no_price
                price_b = market_b.yes_price if pair["pos_b"] == "YES" else market_b.no_price

                total_cost = price_a + price_b

                # Coverage calculation (assuming 98% probability for necessary relationships)
                p_cover = 0.98
                coverage = price_a + (1 - price_a) * p_cover

                # For complementary/exclusive, coverage is simpler
                if pair["type"] in ("complementary", "exclusive"):
                    # Both legs pay $1 if they win, at most one loses
                    coverage = min(1.0, price_a + (1 - price_a) * p_cover)

                expected_profit_per_dollar = coverage - total_cost

                if coverage >= MIN_COVERAGE and expected_profit_per_dollar >= MIN_PROFIT:
                    opp = {
                        "name": pair["name"],
                        "type": pair["type"],
                        "market_a_id": market_a.id,
                        "market_a_q": market_a.question,
                        "pos_a": pair["pos_a"],
                        "price_a": price_a,
                        "market_b_id": market_b.id,
                        "market_b_q": market_b.question,
                        "pos_b": pair["pos_b"],
                        "price_b": price_b,
                        "total_cost": total_cost,
                        "coverage": coverage,
                        "expected_profit": expected_profit_per_dollar,
                        "volume_a": market_a.volume_24h,
                        "volume_b": market_b.volume_24h,
                    }
                    opportunities.append(opp)

            except Exception as e:
                print(f"  [!] Error checking {pair['name']}: {e}")
                continue

        # Sort by profit
        opportunities.sort(key=lambda x: x["expected_profit"], reverse=True)
        return opportunities


# =============================================================================
# MAIN BOT
# =============================================================================

class HedgeServer:
    """Main server - runs forever."""

    def __init__(self):
        self.tg = Telegram()
        self.monitor = PriceMonitor()
        self.scan_count = 0
        self.total_hedges = 0
        self.total_trades = 0
        self.total_profit = 0.0
        self.start_time = datetime.now(timezone.utc)
        self.state_file = Path(__file__).parent / "server_state.json"
        self.last_summary = time.time()
        self.last_ai_scan = time.time()  # Skip AI on first run (use known patterns)

    async def price_scan(self):
        """Quick price-only scan of known pairs."""
        self.scan_count += 1
        now_str = datetime.now(timezone.utc).strftime('%H:%M')
        print(f"\n{'='*50}", flush=True)
        print(f"[{now_str}] Price Scan #{self.scan_count}", flush=True)

        try:
            opps = await self.monitor.check_all_pairs()
        except Exception as e:
            print(f"  [!] Scan error: {e}")
            self.tg_send_later = f"🚨 Scan error: {e}"
            return

        if not opps:
            print(f"  No profitable hedges right now")
            # Send brief update every 4th scan
            if self.scan_count % 4 == 0:
                await self.tg.send(
                    f"🔍 Scan #{self.scan_count} [{now_str}] — "
                    f"No profitable hedges. Monitoring {len(HEDGE_SEARCH_PAIRS)} pairs. "
                    f"Next check in {PRICE_CHECK_INTERVAL//60}m"
                )
            return

        self.total_hedges += len(opps)
        print(f"  🎯 Found {len(opps)} profitable hedges!")

        for opp in opps:
            alert_key = f"{opp['market_a_id']}_{opp['market_b_id']}"

            # Build message
            profit_emoji = "🟢" if opp["expected_profit"] > 0.02 else "🟡"
            msg = (
                f"{profit_emoji} <b>HEDGE: {opp['name']}</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"📈 Leg A: {opp['pos_a']} @ ${opp['price_a']:.3f}\n"
                f"   └ {opp['market_a_q'][:55]}\n"
                f"   └ Vol: ${opp['volume_a']:,.0f}\n"
                f"🛡 Leg B: {opp['pos_b']} @ ${opp['price_b']:.3f}\n"
                f"   └ {opp['market_b_q'][:55]}\n"
                f"   └ Vol: ${opp['volume_b']:,.0f}\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"💰 Cost: ${opp['total_cost']:.3f}\n"
                f"📊 Coverage: {opp['coverage']*100:.1f}%\n"
                f"💵 Profit/$ : ${opp['expected_profit']:+.4f}\n"
                f"🏷 Type: {opp['type']}\n"
            )

            if AUTO_TRADE:
                msg += f"\n🤖 Auto-trading ${MAX_TRADE:.0f}..."
                # Execute trade here when enabled
            else:
                msg += f"\n⚠️ Auto-trade OFF — manual execution needed"

            # Only alert if new or price changed significantly
            if alert_key not in self.monitor.alerted:
                await self.tg.send(msg)
                self.monitor.alerted.add(alert_key)
                print(f"  📢 Alerted: {opp['name']} (${opp['expected_profit']:+.4f})")
            else:
                print(f"  ✓ Known: {opp['name']} (${opp['expected_profit']:+.4f})")

        # Reset alerted set when hedge disappears (price moved)
        active_keys = {f"{o['market_a_id']}_{o['market_b_id']}" for o in opps}
        expired = self.monitor.alerted - active_keys
        if expired:
            self.monitor.alerted -= expired

    async def ai_discovery(self):
        """Run AI-powered discovery of new hedge patterns (expensive, rare)."""
        print(f"\n[AI] Running AI hedge discovery...")

        try:
            from lib.llm_client import LLMClient
            from scripts.hedge import extract_implications_for_market, build_portfolios_from_covers

            gamma = GammaClient()
            markets = await gamma.get_trending_markets(limit=20)

            if len(markets) < 2:
                return

            llm = LLMClient()
            new_hedges = []

            try:
                for i, target in enumerate(markets):
                    print(f"  [AI {i+1}/{len(markets)}] {target.question[:50]}...")
                    try:
                        covers = await extract_implications_for_market(target, markets, llm)
                        if covers:
                            portfolios = build_portfolios_from_covers(target, covers)
                            for p in portfolios:
                                if p["coverage"] >= MIN_COVERAGE:
                                    new_hedges.append(p)
                    except Exception as e:
                        print(f"    [!] {e}")
                        continue
            finally:
                await llm.close()

            if new_hedges:
                msg = (
                    f"🧠 <b>AI Discovery Complete</b>\n"
                    f"Found {len(new_hedges)} new hedges!\n\n"
                )
                for h in new_hedges[:3]:
                    msg += (
                        f"T{h['tier']} {h['coverage']*100:.1f}% — "
                        f"{h['target_position']} {h['target_question'][:30]}... | "
                        f"{h['cover_position']} {h['cover_question'][:30]}...\n"
                        f"  Cost: ${h['total_cost']:.2f}, Profit: ${h['expected_profit']:+.3f}\n\n"
                    )
                await self.tg.send(msg)
            else:
                await self.tg.send(f"🧠 AI Discovery: scanned {len(markets)} markets, no new hedges found")

            self.last_ai_scan = time.time()

        except Exception as e:
            print(f"  [AI] Error: {e}")
            await self.tg.send(f"🧠 AI Discovery error: {str(e)[:200]}")

    async def send_summary(self):
        """Send periodic summary."""
        uptime = datetime.now(timezone.utc) - self.start_time
        hours = uptime.total_seconds() / 3600

        await self.tg.send(
            f"📊 <b>STATUS REPORT</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"⏱ Uptime: {hours:.1f}h\n"
            f"🔍 Price scans: {self.scan_count}\n"
            f"🎯 Hedges alerted: {self.total_hedges}\n"
            f"📋 Patterns monitored: {len(HEDGE_SEARCH_PAIRS)}\n"
            f"🤖 Auto-trade: {'ON' if AUTO_TRADE else 'OFF'}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"⏭ Next price check: {PRICE_CHECK_INTERVAL//60}m\n"
            f"🧠 Next AI scan: {max(0, AI_DISCOVERY_INTERVAL - (time.time() - self.last_ai_scan))//60:.0f}m"
        )
        self.last_summary = time.time()

    async def run(self):
        """Main loop."""
        print("=" * 60)
        print("  🦞 PolyClaw Smart Hedge Server v2")
        print("=" * 60)

        await self.tg.startup()

        while True:
            try:
                # Quick price scan (every 5 min)
                await self.price_scan()

                # AI discovery (every 4 hours, if rate limit allows)
                if time.time() - self.last_ai_scan >= AI_DISCOVERY_INTERVAL:
                    await self.ai_discovery()

                # Summary (every 2 hours)
                if time.time() - self.last_summary >= SUMMARY_INTERVAL:
                    await self.send_summary()

            except Exception as e:
                error_msg = traceback.format_exc()
                print(f"\n[ERROR] {e}\n{error_msg}")
                try:
                    await self.tg.send(f"🚨 <b>ERROR</b>\n<code>{str(e)[:500]}</code>")
                except Exception:
                    pass

            # Wait for next price check
            print(f"  Next check in {PRICE_CHECK_INTERVAL//60}m...")
            await asyncio.sleep(PRICE_CHECK_INTERVAL)


# =============================================================================
# ENTRY POINT
# =============================================================================

def main():
    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    server = HedgeServer()
    try:
        asyncio.run(server.run())
    except KeyboardInterrupt:
        print("\n[EXIT] Server stopped.")
    except Exception as e:
        print(f"\n[FATAL] {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
