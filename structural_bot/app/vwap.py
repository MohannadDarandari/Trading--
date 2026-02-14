from __future__ import annotations

from typing import Iterable, Tuple


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
