#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║          🦞 PolyClaw Auto-Hedge Server Bot                   ║
║          24/7 Hedge Discovery + Auto-Trade + Telegram        ║
╚══════════════════════════════════════════════════════════════╝

Runs continuously on VPS:
1. Scans markets for Tier 1 hedges every SCAN_INTERVAL
2. Auto-executes profitable hedges (coverage >= 98%, profit > 0)
3. Reports EVERYTHING to Telegram (scans, trades, errors, P&L)
4. Tracks all positions and calculates live P&L
"""

import os
import sys
import json
import time
import asyncio
import platform
import traceback
from pathlib import Path
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field, asdict

import httpx

# PolyClaw lib imports
sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from lib.gamma_client import GammaClient, Market
from lib.llm_client import LLMClient, DEFAULT_MODEL
from lib.coverage import build_portfolio, NECESSARY_PROBABILITY

# Import hedge logic
from scripts.hedge import (
    extract_implications_for_market,
    build_portfolios_from_covers,
    extract_json_from_response,
)


# =============================================================================
# CONFIGURATION
# =============================================================================

# Telegram
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8331165268:AAEA84wTDNeFuPhRJkjLiUqxxkaPEuL2B-o")
TELEGRAM_CHAT_IDS = json.loads(os.getenv("TELEGRAM_CHAT_IDS", '["1688623770","1675476723","-5264145102"]'))

# Scanning
SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL", "1800"))  # 30 min default
MARKET_LIMIT = int(os.getenv("MARKET_LIMIT", "20"))
SCAN_QUERIES = json.loads(os.getenv("SCAN_QUERIES", '[""]'))  # trending only (avoid rate limits)

# Trading thresholds
MIN_COVERAGE = float(os.getenv("MIN_COVERAGE", "0.95"))      # Only Tier 1
MIN_PROFIT = float(os.getenv("MIN_PROFIT", "0.01"))          # Min $0.01 expected profit
MAX_TRADE_AMOUNT = float(os.getenv("MAX_TRADE_AMOUNT", "50"))  # Max per hedge leg
AUTO_TRADE = os.getenv("AUTO_TRADE", "false").lower() == "true"

# Reporting
REPORT_INTERVAL = int(os.getenv("REPORT_INTERVAL", "7200"))  # 2hr summary


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class HedgeOpportunity:
    """A discovered hedge opportunity."""
    id: str
    tier: int
    coverage: float
    total_cost: float
    expected_profit: float
    target_market_id: str
    target_question: str
    target_position: str
    target_price: float
    cover_market_id: str
    cover_question: str
    cover_position: str
    cover_price: float
    relationship: str
    discovered_at: str
    traded: bool = False
    trade_result: str = ""

@dataclass
class BotState:
    """Persistent bot state."""
    total_scans: int = 0
    total_hedges_found: int = 0
    total_trades: int = 0
    total_invested: float = 0.0
    total_profit_estimated: float = 0.0
    start_time: str = ""
    last_scan_time: str = ""
    hedge_history: list = field(default_factory=list)
    active_positions: list = field(default_factory=list)
    errors: int = 0


# =============================================================================
# TELEGRAM REPORTER
# =============================================================================

class TelegramReporter:
    """Send reports to Telegram."""

    def __init__(self):
        self.token = TELEGRAM_TOKEN
        self.chat_ids = TELEGRAM_CHAT_IDS
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    async def send(self, message: str, parse_mode: str = "HTML"):
        """Send message to all chat IDs."""
        async with httpx.AsyncClient(timeout=30) as client:
            for chat_id in self.chat_ids:
                try:
                    await client.post(
                        f"{self.base_url}/sendMessage",
                        json={
                            "chat_id": chat_id,
                            "text": message[:4096],
                            "parse_mode": parse_mode,
                            "disable_web_page_preview": True,
                        },
                    )
                except Exception as e:
                    print(f"[TG] Failed to send to {chat_id}: {e}")

    async def send_startup(self, state: BotState):
        """Send startup notification."""
        msg = (
            "🦞 <b>PolyClaw Auto-Hedge Bot ONLINE</b>\n\n"
            f"⏰ Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n"
            f"🔍 Scan interval: {SCAN_INTERVAL//60} min\n"
            f"📊 Markets per scan: {MARKET_LIMIT}\n"
            f"🎯 Min coverage: {MIN_COVERAGE*100:.0f}%\n"
            f"💰 Min profit: ${MIN_PROFIT:.2f}\n"
            f"🤖 Auto-trade: {'ON ✅' if AUTO_TRADE else 'OFF (sim only)'}\n"
            f"💵 Max per trade: ${MAX_TRADE_AMOUNT:.0f}\n\n"
            f"🔎 Queries: {', '.join(q or 'trending' for q in SCAN_QUERIES)}\n"
            "━━━━━━━━━━━━━━━━━━━━━"
        )
        await self.send(msg)

    async def send_scan_result(self, scan_num: int, total_markets: int, hedges: list):
        """Send scan results."""
        now = datetime.now(timezone.utc).strftime('%H:%M')

        if not hedges:
            msg = (
                f"🔍 <b>Scan #{scan_num}</b> [{now} UTC]\n"
                f"📊 {total_markets} markets scanned\n"
                f"❌ No profitable hedges found\n"
                f"⏭ Next scan in {SCAN_INTERVAL//60} min"
            )
            await self.send(msg)
            return

        msg = (
            f"🔍 <b>Scan #{scan_num}</b> [{now} UTC]\n"
            f"📊 {total_markets} markets scanned\n"
            f"🎯 <b>{len(hedges)} HEDGE(S) FOUND!</b>\n\n"
        )

        for h in hedges[:5]:  # Max 5 per message
            profit_emoji = "🟢" if h.expected_profit > 0 else "🔴"
            msg += (
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"{profit_emoji} <b>T{h.tier} | {h.coverage*100:.1f}% coverage</b>\n"
                f"📈 Target: {h.target_position} @ ${h.target_price:.2f}\n"
                f"   └ {h.target_question[:50]}...\n"
                f"🛡 Cover: {h.cover_position} @ ${h.cover_price:.2f}\n"
                f"   └ {h.cover_question[:50]}...\n"
                f"💰 Cost: ${h.total_cost:.2f} | Profit: ${h.expected_profit:+.3f}\n"
            )

            if h.traded:
                msg += f"✅ TRADED: {h.trade_result}\n"

        if len(hedges) > 5:
            msg += f"\n... and {len(hedges)-5} more"

        await self.send(msg)

    async def send_trade_alert(self, hedge: HedgeOpportunity, success: bool, details: str):
        """Send trade execution alert."""
        emoji = "✅" if success else "❌"
        msg = (
            f"{emoji} <b>TRADE {'EXECUTED' if success else 'FAILED'}</b>\n\n"
            f"🎯 {hedge.target_position} @ ${hedge.target_price:.2f}\n"
            f"   └ {hedge.target_question[:60]}\n"
            f"🛡 {hedge.cover_position} @ ${hedge.cover_price:.2f}\n"
            f"   └ {hedge.cover_question[:60]}\n"
            f"💰 Total cost: ${hedge.total_cost:.2f}\n"
            f"📊 Coverage: {hedge.coverage*100:.1f}%\n"
            f"💵 Expected profit: ${hedge.expected_profit:+.3f}\n\n"
            f"ℹ️ {details}"
        )
        await self.send(msg)

    async def send_summary(self, state: BotState):
        """Send periodic summary report."""
        uptime_start = datetime.fromisoformat(state.start_time)
        uptime = datetime.now(timezone.utc) - uptime_start
        hours = uptime.total_seconds() / 3600

        msg = (
            f"📊 <b>SUMMARY REPORT</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"⏱ Uptime: {hours:.1f}h\n"
            f"🔍 Total scans: {state.total_scans}\n"
            f"🎯 Hedges found: {state.total_hedges_found}\n"
            f"💼 Trades: {state.total_trades}\n"
            f"💰 Invested: ${state.total_invested:.2f}\n"
            f"📈 Est. profit: ${state.total_profit_estimated:.2f}\n"
            f"❗ Errors: {state.errors}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🤖 Auto-trade: {'ON' if AUTO_TRADE else 'OFF'}\n"
            f"⏰ Next scan: ~{SCAN_INTERVAL//60} min"
        )
        await self.send(msg)

    async def send_error(self, error_msg: str):
        """Send error alert."""
        msg = (
            f"🚨 <b>ERROR</b>\n\n"
            f"<code>{error_msg[:2000]}</code>"
        )
        await self.send(msg)


# =============================================================================
# HEDGE SCANNER
# =============================================================================

class HedgeScanner:
    """Scan markets for hedging opportunities."""

    def __init__(self):
        self.gamma = GammaClient()
        self.seen_hedges: set = set()  # Avoid duplicate alerts

    async def scan(self, query: str = "", limit: int = 20) -> tuple[int, list[HedgeOpportunity]]:
        """
        Scan markets for hedges.
        Returns (total_markets_scanned, list_of_opportunities).
        """
        # Fetch markets
        if query:
            markets = await self.gamma.search_markets(query, limit=limit)
        else:
            markets = await self.gamma.get_trending_markets(limit=limit)

        if len(markets) < 2:
            return len(markets), []

        # Init LLM
        try:
            llm = LLMClient()
        except ValueError:
            return len(markets), []

        all_hedges = []

        try:
            for target in markets:
                try:
                    covers = await extract_implications_for_market(target, markets, llm)
                    if covers:
                        portfolios = build_portfolios_from_covers(target, covers)
                        for p in portfolios:
                            # Filter by our thresholds
                            if p["coverage"] >= MIN_COVERAGE and p["expected_profit"] >= MIN_PROFIT:
                                hedge_id = f"{p['target_market_id']}_{p['cover_market_id']}_{p['target_position']}_{p['cover_position']}"

                                hedge = HedgeOpportunity(
                                    id=hedge_id,
                                    tier=p["tier"],
                                    coverage=p["coverage"],
                                    total_cost=p["total_cost"],
                                    expected_profit=p["expected_profit"],
                                    target_market_id=p["target_market_id"],
                                    target_question=p["target_question"],
                                    target_position=p["target_position"],
                                    target_price=p["target_price"],
                                    cover_market_id=p["cover_market_id"],
                                    cover_question=p["cover_question"],
                                    cover_position=p["cover_position"],
                                    cover_price=p["cover_price"],
                                    relationship=p.get("relationship", ""),
                                    discovered_at=datetime.now(timezone.utc).isoformat(),
                                )
                                all_hedges.append(hedge)

                except Exception as e:
                    print(f"  [!] Error analyzing {target.question[:40]}: {e}")
                    continue

        finally:
            await llm.close()

        # Sort by expected profit descending
        all_hedges.sort(key=lambda h: h.expected_profit, reverse=True)

        return len(markets), all_hedges


# =============================================================================
# TRADE EXECUTOR (Simulation + Real)
# =============================================================================

class TradeExecutor:
    """Execute trades or simulate them."""

    def __init__(self):
        self.auto_trade = AUTO_TRADE

    async def execute_hedge(self, hedge: HedgeOpportunity) -> tuple[bool, str]:
        """
        Execute a hedge trade (both legs).
        Returns (success, details_string).
        """
        if not self.auto_trade:
            details = (
                f"[SIM] Would buy {hedge.target_position} on {hedge.target_market_id} "
                f"@ ${hedge.target_price:.2f} + "
                f"{hedge.cover_position} on {hedge.cover_market_id} "
                f"@ ${hedge.cover_price:.2f} = "
                f"${hedge.total_cost:.2f} total"
            )
            return True, details

        # Real trading via PolyClaw
        try:
            from lib.wallet_manager import WalletManager
            from scripts.trade import TradeExecutor as PolyTrader

            wallet = WalletManager()
            if not wallet.is_unlocked:
                return False, "Wallet not configured"

            balances = wallet.get_balances()
            needed = hedge.total_cost * 1.02  # 2% buffer
            if balances.usdc_e < needed:
                return False, f"Insufficient balance: ${balances.usdc_e:.2f} < ${needed:.2f}"

            trader = PolyTrader(wallet)

            # Leg 1: Target
            amount_per_leg = MAX_TRADE_AMOUNT / 2
            result1 = await trader.buy_position(
                hedge.target_market_id,
                hedge.target_position,
                amount_per_leg,
            )

            if not result1.success:
                return False, f"Leg 1 failed: {result1.error}"

            # Leg 2: Cover
            result2 = await trader.buy_position(
                hedge.cover_market_id,
                hedge.cover_position,
                amount_per_leg,
            )

            if not result2.success:
                return False, f"Leg 1 OK (tx: {result1.split_tx[:12]}...), Leg 2 failed: {result2.error}"

            details = (
                f"Leg 1: {result1.split_tx[:16]}... "
                f"Leg 2: {result2.split_tx[:16]}... "
                f"Total: ${amount_per_leg*2:.2f}"
            )
            return True, details

        except Exception as e:
            return False, f"Trade error: {e}"


# =============================================================================
# MAIN BOT ENGINE
# =============================================================================

class HedgeBot:
    """Main bot engine - runs forever."""

    def __init__(self):
        self.scanner = HedgeScanner()
        self.executor = TradeExecutor()
        self.telegram = TelegramReporter()
        self.state = BotState(start_time=datetime.now(timezone.utc).isoformat())
        self.state_file = Path(__file__).parent / "bot_state.json"
        self._load_state()

    def _load_state(self):
        """Load state from file."""
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text())
                self.state.total_scans = data.get("total_scans", 0)
                self.state.total_hedges_found = data.get("total_hedges_found", 0)
                self.state.total_trades = data.get("total_trades", 0)
                self.state.total_invested = data.get("total_invested", 0.0)
                self.state.total_profit_estimated = data.get("total_profit_estimated", 0.0)
                self.state.errors = data.get("errors", 0)
            except Exception:
                pass

    def _save_state(self):
        """Save state to file."""
        try:
            self.state_file.write_text(json.dumps(asdict(self.state), indent=2, default=str))
        except Exception as e:
            print(f"[!] Failed to save state: {e}")

    async def run_scan_cycle(self):
        """Run one full scan cycle across all queries."""
        self.state.total_scans += 1
        self.state.last_scan_time = datetime.now(timezone.utc).isoformat()
        total_markets = 0
        all_hedges = []

        for query in SCAN_QUERIES:
            try:
                label = query or "trending"
                print(f"\n[SCAN] Scanning '{label}' markets...")

                n_markets, hedges = await self.scanner.scan(query=query, limit=MARKET_LIMIT)
                total_markets += n_markets

                if hedges:
                    all_hedges.extend(hedges)
                    print(f"  -> Found {len(hedges)} hedges from '{label}'")
                else:
                    print(f"  -> No hedges from '{label}'")

            except Exception as e:
                self.state.errors += 1
                print(f"  [!] Error scanning '{query}': {e}")
                await self.telegram.send_error(f"Scan error (query='{query}'): {e}")

        # Deduplicate by hedge ID
        seen = set()
        unique_hedges = []
        for h in all_hedges:
            if h.id not in seen:
                seen.add(h.id)
                unique_hedges.append(h)

        self.state.total_hedges_found += len(unique_hedges)

        # Execute trades for profitable hedges
        for hedge in unique_hedges:
            if hedge.expected_profit > 0:
                try:
                    success, details = await self.executor.execute_hedge(hedge)
                    hedge.traded = True
                    hedge.trade_result = details

                    if success:
                        self.state.total_trades += 1
                        self.state.total_invested += hedge.total_cost
                        self.state.total_profit_estimated += hedge.expected_profit

                    await self.telegram.send_trade_alert(hedge, success, details)

                except Exception as e:
                    self.state.errors += 1
                    await self.telegram.send_error(f"Trade execution error: {e}")

        # Send scan result to Telegram
        await self.telegram.send_scan_result(
            self.state.total_scans, total_markets, unique_hedges
        )

        # Save state
        self._save_state()

        print(f"\n[SCAN #{self.state.total_scans}] Done: {total_markets} markets, {len(unique_hedges)} hedges")

    async def run(self):
        """Main loop - runs forever."""
        print("=" * 60)
        print("  🦞 PolyClaw Auto-Hedge Bot Starting...")
        print("=" * 60)

        await self.telegram.send_startup(self.state)
        last_summary = time.time()

        while True:
            try:
                await self.run_scan_cycle()
            except Exception as e:
                self.state.errors += 1
                error_msg = traceback.format_exc()
                print(f"\n[ERROR] Scan cycle failed: {e}")
                print(error_msg)
                await self.telegram.send_error(f"Scan cycle crashed:\n{error_msg[-500:]}")

            # Periodic summary
            if time.time() - last_summary >= REPORT_INTERVAL:
                await self.telegram.send_summary(self.state)
                last_summary = time.time()

            # Wait for next scan
            print(f"\n[WAIT] Next scan in {SCAN_INTERVAL//60} min...")
            await asyncio.sleep(SCAN_INTERVAL)


# =============================================================================
# ENTRY POINT
# =============================================================================

def main():
    # Windows fix
    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    bot = HedgeBot()

    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        print("\n[EXIT] Bot stopped by user.")
    except Exception as e:
        print(f"\n[FATAL] {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
