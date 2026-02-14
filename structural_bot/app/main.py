from __future__ import annotations

import asyncio
import os
import time
import yaml
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

from .db import DB
from .gamma import GammaClient
from .polymarket_clob import PolymarketCLOB, normalize_levels
from .vwap import vwap_cost, best_spread
from .risk import RiskLimits, RiskManager
from .telegram import TelegramBot
from .correlation import SpotFeatureBuffer, lag_detector
from .exec import place_two_sided, wait_for_fills, cancel_order, flatten_side, simulate_paper_execution


BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config.yml"
DB_PATH = BASE_DIR / "data" / "polyscan_live.db"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def fetch_spot_price(symbol: str) -> float | None:
    """Fetch spot price from a public endpoint (Coinbase)."""
    url = f"https://api.coinbase.com/v2/prices/{symbol}-USD/spot"
    try:
        async with httpx.AsyncClient(timeout=5) as http:
            resp = await http.get(url)
            resp.raise_for_status()
            data = resp.json()
            return float(data["data"]["amount"])
    except Exception:
        return None


def compute_threshold(cfg: dict) -> float:
    b = cfg["buffers"]
    return 1.0 - (b["fee_buffer"] + b["slippage_buffer"] + b["safety_margin"])


def market_time_to_close(end_time: str) -> float:
    try:
        end = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
        return (end - datetime.now(timezone.utc)).total_seconds()
    except Exception:
        return 9999


class RateLimiter:
    def __init__(self, max_per_sec: int) -> None:
        self.max_per_sec = max_per_sec
        self.calls: list[float] = []

    async def wait(self) -> None:
        now = time.time()
        self.calls = [t for t in self.calls if now - t <= 1.0]
        if len(self.calls) >= self.max_per_sec:
            sleep_for = 1.0 - (now - self.calls[0])
            if sleep_for > 0:
                await asyncio.sleep(sleep_for)
        self.calls.append(time.time())


def csv_from_rows(rows: list[dict], header: list[str]) -> str:
    lines = [",".join(header)]
    for r in rows:
        lines.append(",".join(str(r.get(h, "")) for h in header))
    return "\n".join(lines)


async def main() -> None:
    load_dotenv(BASE_DIR / ".env")

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    db = DB(str(DB_PATH))
    tg = TelegramBot()

    risk = RiskManager(RiskLimits(**cfg["risk"]))
    bankroll = float(cfg.get("bankroll_usd", 0))

    live_enabled = os.getenv("LIVE_ENABLED", "false").lower() == "true"
    threshold = compute_threshold(cfg)
    limiter = RateLimiter(int(cfg["max_requests_per_sec"]))

    gamma = GammaClient(os.getenv("POLYMARKET_GAMMA_BASE_URL", "https://gamma-api.polymarket.com"))

    markets_cached = db.get_cached_markets()
    if markets_cached:
        market_map = {row["symbol"]: row for row in markets_cached}
    else:
        markets = await gamma.get_markets(limit=300)
        discovered = gamma.discover_15m_markets(markets)
        market_map = {}
        for symbol, m in discovered.items():
            db.insert_market(utc_now(), symbol, m.id, m.yes_token_id, m.no_token_id or "", m.question, m.end_date)
            market_map[symbol] = {
                "symbol": symbol,
                "market_id": m.id,
                "yes_token_id": m.yes_token_id,
                "no_token_id": m.no_token_id or "",
                "question": m.question,
                "end_time": m.end_date,
            }

    clob = PolymarketCLOB(
        os.getenv("POLYMARKET_CLOB_BASE_URL", "https://clob.polymarket.com"),
        cfg.get("clob", {}),
    )

    spot_buffers = {"BTC": SpotFeatureBuffer(), "ETH": SpotFeatureBuffer()}

    last_report = time.time()
    daily_report_hour = cfg["reporting"]["daily_report_utc_hour"]

    await tg.send_message("✅ Structural bot started (simulation by default)")

    while True:
        tick_start = time.time()

        # Spot price feed (1s)
        for sym, key in [("BTC", "BTC"), ("ETH", "ETH")]:
            price = await fetch_spot_price(sym)
            if price:
                buf = spot_buffers[key]
                buf.add(price)
                ret_15, ret_60 = buf.returns()
                vol_60 = buf.realized_vol()
                momentum = 1 if (ret_15 or 0) > 0 else -1 if (ret_15 or 0) < 0 else 0
                db.insert_external_price(
                    ts=utc_now(),
                    symbol=sym,
                    price=price,
                    ret_15s=ret_15,
                    ret_60s=ret_60,
                    vol_60s=vol_60,
                    momentum=momentum,
                )

        # Scan markets
        for symbol, m in market_map.items():
            try:
                end_time = m["end_time"]
                ttc = market_time_to_close(end_time)
                if ttc < cfg["min_time_to_close_sec"]:
                    continue

                await limiter.wait()
                yes_book = await clob.get_orderbook(m["yes_token_id"], cfg["depth_levels"])
                await limiter.wait()
                no_book = await clob.get_orderbook(m["no_token_id"], cfg["depth_levels"])

                yes_asks = normalize_levels(yes_book.get("asks", []))
                yes_bids = normalize_levels(yes_book.get("bids", []))
                no_asks = normalize_levels(no_book.get("asks", []))
                no_bids = normalize_levels(no_book.get("bids", []))

                spread_yes = best_spread(yes_bids, yes_asks)
                spread_no = best_spread(no_bids, no_asks)
                spread_ok = int(spread_yes <= cfg["spread_max"] and spread_no <= cfg["spread_max"])

                max_cost = cfg["max_total_cost_per_trade_usd"]
                qty = max(1, int(max_cost / max(0.01, threshold)))

                yes_cost, yes_ok = vwap_cost(yes_asks, qty)
                no_cost, no_ok = vwap_cost(no_asks, qty)
                depth_ok = int(yes_ok and no_ok)

                unit_cost = (yes_cost + no_cost) / qty if qty > 0 else 999

                db.insert_scan(
                    ts=utc_now(),
                    market_symbol=symbol,
                    unit_cost=unit_cost,
                    threshold=threshold,
                    yes_vwap=yes_cost / qty if qty else None,
                    no_vwap=no_cost / qty if qty else None,
                    depth_ok=depth_ok,
                    spread_ok=spread_ok,
                    time_to_close_sec=ttc,
                    latency_ms=(time.time() - tick_start) * 1000,
                    error=None,
                )

                # Correlation signals (simulation only)
                buf = spot_buffers["BTC" if "BTC" in symbol else "ETH"]
                ret_30 = None
                try:
                    p_30 = buf._price_at(30)
                    latest = buf.points[-1].price if buf.points else None
                    if p_30 and latest:
                        ret_30 = (latest - p_30) / p_30
                except Exception:
                    ret_30 = None

                pm_move = 0.0
                if yes_bids and yes_asks:
                    pm_mid = (yes_bids[0][0] + yes_asks[0][0]) / 2
                    pm_move = pm_mid - (yes_bids[0][0])

                if ret_30 is not None:
                    lag, score = lag_detector(ret_30, pm_move)
                    db.insert_correlation(
                        ts=utc_now(),
                        symbol=symbol,
                        spot_move_30s=ret_30,
                        pm_move_30s=pm_move,
                        lag_flag=int(lag),
                        score=score,
                    )

                # Entry signal (structural only)
                if unit_cost <= threshold and depth_ok and spread_ok:
                    if live_enabled and risk.can_take_trade(bankroll, cfg["max_total_cost_per_trade_usd"]):
                        best_yes_ask = yes_asks[0][0] if yes_asks else None
                        best_no_ask = no_asks[0][0] if no_asks else None
                        best_yes_bid = yes_bids[0][0] if yes_bids else None
                        best_no_bid = no_bids[0][0] if no_bids else None

                        if best_yes_ask and best_no_ask and best_yes_bid and best_no_bid:
                            id_yes = f"{m['market_id']}_YES_{int(time.time()*1000)}"
                            id_no = f"{m['market_id']}_NO_{int(time.time()*1000)}"

                            risk.add_exposure(cfg["max_total_cost_per_trade_usd"])
                            risk.record_trade()

                            res_yes, res_no = await place_two_sided(
                                clob,
                                m["yes_token_id"],
                                m["no_token_id"],
                                best_yes_ask,
                                best_no_ask,
                                qty,
                                id_yes,
                                id_no,
                            )

                            db.insert_order(ts=utc_now(), market_id=m["market_id"], side="YES", price=best_yes_ask, size=qty, status="submitted", idempotency_key=id_yes, clob_order_id=res_yes.order_id, error=res_yes.error)
                            db.insert_order(ts=utc_now(), market_id=m["market_id"], side="NO", price=best_no_ask, size=qty, status="submitted", idempotency_key=id_no, clob_order_id=res_no.order_id, error=res_no.error)

                            if res_yes.ok and res_no.ok and res_yes.order_id and res_no.order_id:
                                filled_yes, filled_no = await wait_for_fills(clob, res_yes.order_id, res_no.order_id, timeout_sec=2.0)
                                if filled_yes > 0 and filled_no > 0:
                                    risk.record_hedged_complete()
                                    await tg.send_message(f"HEDGED_COMPLETE: {symbol} qty={qty}")
                                else:
                                    risk.record_partial_fill()
                                    await cancel_order(clob, res_yes.order_id)
                                    await cancel_order(clob, res_no.order_id)

                                    if filled_yes > 0 and best_yes_bid:
                                        await flatten_side(clob, m["yes_token_id"], best_yes_bid, filled_yes, f"FLAT_Y_{id_yes}")
                                    if filled_no > 0 and best_no_bid:
                                        await flatten_side(clob, m["no_token_id"], best_no_bid, filled_no, f"FLAT_N_{id_no}")

                                    db.insert_incident(ts=utc_now(), incident_type="partial_fill", market_id=m["market_id"], details=f"yes={filled_yes} no={filled_no}")
                                    await tg.send_message(f"PARTIAL_FILL: {symbol} yes={filled_yes} no={filled_no}")
                            else:
                                db.insert_incident(ts=utc_now(), incident_type="order_error", market_id=m["market_id"], details=f"yes={res_yes.error} no={res_no.error}")
                                await tg.send_message(f"ORDER_ERROR: {symbol}")

                            risk.reduce_exposure(cfg["max_total_cost_per_trade_usd"])
                        else:
                            await tg.send_message(f"LIVE skipped: missing best prices for {symbol}")
                    else:
                        sim = await simulate_paper_execution(unit_cost, threshold)
                        db.insert_incident(ts=utc_now(), incident_type="sim_trade", market_id=m["market_id"], details=f"edge={sim['edge']:.4f}|class={sim['classification']}")
                        await tg.send_message(f"SIM signal: {symbol} unit_cost={unit_cost:.4f} edge={sim['edge']:.4f}")

            except Exception as e:
                risk.record_api_error()
                db.insert_scan(
                    ts=utc_now(),
                    market_symbol=symbol,
                    unit_cost=None,
                    threshold=threshold,
                    yes_vwap=None,
                    no_vwap=None,
                    depth_ok=0,
                    spread_ok=0,
                    time_to_close_sec=None,
                    latency_ms=(time.time() - tick_start) * 1000,
                    error=str(e)[:200],
                )

        if risk.should_kill():
            await tg.send_message(f"KILL SWITCH: {risk.kill_reason}")
            db.insert_incident(ts=utc_now(), incident_type="kill_switch", market_id=None, details=risk.kill_reason)
            break

        # Periodic report
        if time.time() - last_report >= cfg["reporting"]["telegram_interval_sec"]:
            orders = [dict(r) for r in db.fetch_recent("orders", 200)]
            fills = [dict(r) for r in db.fetch_recent("fills", 200)]
            incidents = [dict(r) for r in db.fetch_recent("incidents", 200)]

            orders_csv = csv_from_rows(orders, ["ts", "market_id", "side", "price", "size", "status", "idempotency_key", "clob_order_id", "error"])
            fills_csv = csv_from_rows(fills, ["ts", "order_id", "market_id", "side", "price", "size", "fee", "pnl_est"])
            incidents_csv = csv_from_rows(incidents, ["ts", "incident_type", "market_id", "details"])

            await tg.send_message("Periodic report: structural bot running")
            await tg.send_csv("orders_2h.csv", orders_csv, "Orders (last 2h)")
            await tg.send_csv("fills_2h.csv", fills_csv, "Fills (last 2h)")
            await tg.send_csv("incidents_2h.csv", incidents_csv, "Incidents (last 2h)")
            last_report = time.time()

        # Daily report at midnight UTC
        now = datetime.now(timezone.utc)
        if now.hour == daily_report_hour and now.minute == 0:
            await tg.send_message("Daily report: structural bot status OK")

        elapsed = time.time() - tick_start
        sleep_for = max(0, cfg["scan_interval_sec"] - elapsed)
        await asyncio.sleep(sleep_for)


if __name__ == "__main__":
    if os.name == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
