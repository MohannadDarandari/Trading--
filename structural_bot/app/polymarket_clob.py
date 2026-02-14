from __future__ import annotations

import json
import os
import time
import hmac
import hashlib
from typing import Any

import httpx


class ClobAuth:
    """Placeholder for official Polymarket auth.

    This expects standard API key material in env vars and builds headers.
    Adjust the signature logic to match official documentation.
    """

    def __init__(self) -> None:
        self.api_key = os.getenv("POLYMARKET_AUTH_API_KEY", "")
        self.api_secret = os.getenv("POLYMARKET_AUTH_API_SECRET", "")
        self.passphrase = os.getenv("POLYMARKET_AUTH_PASSPHRASE", "")
        self.account = os.getenv("POLYMARKET_AUTH_ACCOUNT", "")
        self.custom_headers = os.getenv("POLYMARKET_AUTH_HEADERS_JSON", "")

    def build_headers(self, method: str, path: str, body: str) -> dict[str, str]:
        if self.custom_headers:
            try:
                return json.loads(self.custom_headers)
            except Exception:
                return {}

        if not self.api_key or not self.api_secret:
            return {}

        timestamp = str(int(time.time() * 1000))
        message = f"{timestamp}{method.upper()}{path}{body}"
        signature = hmac.new(self.api_secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()

        return {
            "POLY-API-KEY": self.api_key,
            "POLY-API-SIGNATURE": signature,
            "POLY-API-TIMESTAMP": timestamp,
            "POLY-API-PASSPHRASE": self.passphrase,
            "POLY-API-ACCOUNT": self.account,
        }


class PolymarketCLOB:
    def __init__(self, base_url: str, endpoints: dict[str, str]) -> None:
        self.base_url = base_url.rstrip("/")
        self.endpoints = endpoints
        self.auth = ClobAuth()

    async def _request(self, method: str, path: str, params: dict[str, Any] | None = None, json_body: dict[str, Any] | None = None) -> dict[str, Any]:
        body = json.dumps(json_body) if json_body else ""
        headers = self.auth.build_headers(method, path, body)
        async with httpx.AsyncClient(timeout=10) as http:
            resp = await http.request(method, f"{self.base_url}{path}", params=params, json=json_body, headers=headers)
            resp.raise_for_status()
            return resp.json()

    async def get_orderbook(self, token_id: str, depth: int = 10) -> dict[str, Any]:
        path = self.endpoints.get("orderbook_path", "/book")
        return await self._request("GET", path, params={"token_id": token_id, "depth": depth})

    async def place_order(self, order: dict[str, Any]) -> dict[str, Any]:
        path = self.endpoints.get("orders_path", "/orders")
        return await self._request("POST", path, json_body=order)

    async def cancel_order(self, order_id: str) -> dict[str, Any]:
        path = self.endpoints.get("order_path", "/order")
        return await self._request("DELETE", path, params={"order_id": order_id})

    async def list_orders(self) -> dict[str, Any]:
        path = self.endpoints.get("orders_path", "/orders")
        return await self._request("GET", path)

    async def list_fills(self) -> dict[str, Any]:
        path = self.endpoints.get("fills_path", "/fills")
        return await self._request("GET", path)

    async def get_balances(self) -> dict[str, Any]:
        path = self.endpoints.get("balances_path", "/balances")
        return await self._request("GET", path)

    async def get_positions(self) -> dict[str, Any]:
        path = self.endpoints.get("positions_path", "/positions")
        return await self._request("GET", path)


def normalize_levels(levels: list[Any]) -> list[tuple[float, float]]:
    """Normalize orderbook levels to (price, size)."""
    out: list[tuple[float, float]] = []
    for lvl in levels:
        if isinstance(lvl, dict):
            out.append((float(lvl.get("price", 0)), float(lvl.get("size", 0))))
        elif isinstance(lvl, (list, tuple)) and len(lvl) >= 2:
            out.append((float(lvl[0]), float(lvl[1])))
    return out
