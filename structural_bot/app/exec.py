from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

from .polymarket_clob import PolymarketCLOB


@dataclass
class OrderResult:
    ok: bool
    order_id: str | None
    error: str | None


def build_order(token_id: str, price: float, size: float, side: str, idempotency_key: str) -> dict[str, Any]:
    return {
        "token_id": token_id,
        "price": round(price, 4),
        "size": size,
        "side": side,
        "type": "limit",
        "idempotency_key": idempotency_key,
    }


def _extract_filled_sizes(fills: Any, order_id: str) -> float:
    filled = 0.0
    if isinstance(fills, dict):
        data = fills.get("data", fills.get("fills", fills))
    else:
        data = fills

    if isinstance(data, list):
        for f in data:
            try:
                if f.get("order_id") == order_id or f.get("orderId") == order_id:
                    filled += float(f.get("size", f.get("filled", 0)))
            except Exception:
                continue
    return filled


async def place_two_sided(
    clob: PolymarketCLOB,
    yes_token: str,
    no_token: str,
    yes_price: float,
    no_price: float,
    qty: float,
    id_key_yes: str,
    id_key_no: str,
) -> tuple[OrderResult, OrderResult]:
    try:
        yes_order = build_order(yes_token, yes_price, qty, "buy", id_key_yes)
        no_order = build_order(no_token, no_price, qty, "buy", id_key_no)

        res_yes = await clob.place_order(yes_order)
        res_no = await clob.place_order(no_order)

        return OrderResult(True, res_yes.get("id"), None), OrderResult(True, res_no.get("id"), None)
    except Exception as e:
        return OrderResult(False, None, str(e)), OrderResult(False, None, str(e))


async def cancel_order(clob: PolymarketCLOB, order_id: str) -> None:
    try:
        await clob.cancel_order(order_id)
    except Exception:
        return


async def wait_for_fills(clob: PolymarketCLOB, yes_order_id: str, no_order_id: str, timeout_sec: float = 2.0) -> tuple[float, float]:
    start = time.time()
    yes_filled = 0.0
    no_filled = 0.0
    while time.time() - start < timeout_sec:
        try:
            fills = await clob.list_fills()
            yes_filled = _extract_filled_sizes(fills, yes_order_id)
            no_filled = _extract_filled_sizes(fills, no_order_id)
            if yes_filled > 0 and no_filled > 0:
                return yes_filled, no_filled
        except Exception:
            pass
        await asyncio.sleep(0.1)
    return yes_filled, no_filled


async def flatten_side(clob: PolymarketCLOB, token_id: str, price: float, qty: float, id_key: str) -> None:
    try:
        order = build_order(token_id, price, qty, "sell", id_key)
        await clob.place_order(order)
    except Exception:
        return


async def simulate_paper_execution(unit_cost: float, threshold: float, delay_sec: float = 0.3) -> dict[str, str | float]:
    """Paper execution simulator with a short delay and risk classification."""
    await asyncio.sleep(delay_sec)
    edge = threshold - unit_cost
    classification = "HIGH" if edge >= 0.02 else "MEDIUM" if edge >= 0.01 else "LOW"
    return {"status": "SIM_FILLED", "edge": edge, "classification": classification}
