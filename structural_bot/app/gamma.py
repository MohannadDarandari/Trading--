from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import httpx


@dataclass
class GammaMarket:
    id: str
    question: str
    slug: str
    yes_token_id: str
    no_token_id: Optional[str]
    end_date: str
    active: bool
    closed: bool
    resolved: bool


class GammaClient:
    def __init__(self, base_url: str, timeout: float = 20.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def get_markets(self, limit: int = 200) -> list[GammaMarket]:
        async with httpx.AsyncClient(timeout=self.timeout) as http:
            resp = await http.get(
                f"{self.base_url}/markets",
                params={"closed": "false", "limit": limit, "order": "volume24hr", "ascending": "false"},
            )
            resp.raise_for_status()
            return [self._parse_market(m) for m in resp.json()]

    async def search_markets(self, query: str, limit: int = 200) -> list[GammaMarket]:
        markets = await self.get_markets(limit=limit)
        q = query.lower()
        return [m for m in markets if q in (m.question or "").lower() or q in (m.slug or "").lower()]

    def discover_15m_markets(self, markets: list[GammaMarket]) -> dict[str, GammaMarket]:
        """Find BTC/ETH 15m up/down markets deterministically from a list of markets."""
        results: dict[str, GammaMarket] = {}

        def match(m: GammaMarket, asset: str, direction: str) -> bool:
            text = (m.question or "").lower()
            if asset not in text:
                return False
            if "15" not in text and "15m" not in text and "15-minute" not in text:
                return False
            if direction == "up" and "up" not in text:
                return False
            if direction == "down" and "down" not in text:
                return False
            return True

        for m in markets:
            if m.closed or m.resolved:
                continue
            if match(m, "btc", "up") or match(m, "bitcoin", "up"):
                results["BTC_UP"] = m
            if match(m, "btc", "down") or match(m, "bitcoin", "down"):
                results["BTC_DOWN"] = m
            if match(m, "eth", "up") or match(m, "ethereum", "up"):
                results["ETH_UP"] = m
            if match(m, "eth", "down") or match(m, "ethereum", "down"):
                results["ETH_DOWN"] = m

        return results

    def _parse_market(self, data: dict) -> GammaMarket:
        clob_tokens = data.get("clobTokenIds") or "[]"
        try:
            import json
            tokens = json.loads(clob_tokens)
        except Exception:
            tokens = []

        return GammaMarket(
            id=data.get("id", ""),
            question=data.get("question", ""),
            slug=data.get("slug", ""),
            yes_token_id=tokens[0] if tokens else "",
            no_token_id=tokens[1] if len(tokens) > 1 else None,
            end_date=data.get("endDate", ""),
            active=data.get("active", True),
            closed=data.get("closed", False),
            resolved=data.get("resolved", False),
        )
