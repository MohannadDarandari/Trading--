from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS markets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        symbol TEXT NOT NULL,
        market_id TEXT NOT NULL,
        yes_token_id TEXT NOT NULL,
        no_token_id TEXT,
        question TEXT NOT NULL,
        end_time TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        market_symbol TEXT NOT NULL,
        unit_cost REAL,
        threshold REAL,
        yes_vwap REAL,
        no_vwap REAL,
        depth_ok INTEGER,
        spread_ok INTEGER,
        time_to_close_sec REAL,
        latency_ms REAL,
        error TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        market_id TEXT NOT NULL,
        side TEXT NOT NULL,
        price REAL,
        size REAL,
        status TEXT,
        idempotency_key TEXT,
        clob_order_id TEXT,
        error TEXT
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
        fee REAL,
        pnl_est REAL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS positions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        market_id TEXT NOT NULL,
        yes_qty REAL,
        no_qty REAL,
        exposure_usd REAL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS incidents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        incident_type TEXT NOT NULL,
        market_id TEXT,
        details TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS pnl (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        realized REAL,
        unrealized REAL,
        notes TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS external_prices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        symbol TEXT NOT NULL,
        price REAL,
        ret_15s REAL,
        ret_60s REAL,
        vol_60s REAL,
        momentum INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS correlation_signals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        symbol TEXT NOT NULL,
        spot_move_30s REAL,
        pm_move_30s REAL,
        lag_flag INTEGER,
        score REAL
    )
    """,
]


class DB:
    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        cur = self.conn.cursor()
        for ddl in SCHEMA:
            cur.execute(ddl)
        self.conn.commit()

    def insert_market(self, ts: str, symbol: str, market_id: str, yes_token: str, no_token: str | None, question: str, end_time: str) -> None:
        self.conn.execute(
            "INSERT INTO markets (ts, symbol, market_id, yes_token_id, no_token_id, question, end_time) VALUES (?,?,?,?,?,?,?)",
            (ts, symbol, market_id, yes_token, no_token, question, end_time),
        )
        self.conn.commit()

    def get_cached_markets(self) -> list[sqlite3.Row]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM markets ORDER BY id DESC")
        return cur.fetchall()

    def insert_scan(self, **kwargs: Any) -> None:
        keys = ",".join(kwargs.keys())
        values = list(kwargs.values())
        placeholders = ",".join(["?"] * len(values))
        self.conn.execute(f"INSERT INTO scans ({keys}) VALUES ({placeholders})", values)
        self.conn.commit()

    def insert_order(self, **kwargs: Any) -> None:
        keys = ",".join(kwargs.keys())
        values = list(kwargs.values())
        placeholders = ",".join(["?"] * len(values))
        self.conn.execute(f"INSERT INTO orders ({keys}) VALUES ({placeholders})", values)
        self.conn.commit()

    def insert_fill(self, **kwargs: Any) -> None:
        keys = ",".join(kwargs.keys())
        values = list(kwargs.values())
        placeholders = ",".join(["?"] * len(values))
        self.conn.execute(f"INSERT INTO fills ({keys}) VALUES ({placeholders})", values)
        self.conn.commit()

    def insert_position(self, **kwargs: Any) -> None:
        keys = ",".join(kwargs.keys())
        values = list(kwargs.values())
        placeholders = ",".join(["?"] * len(values))
        self.conn.execute(f"INSERT INTO positions ({keys}) VALUES ({placeholders})", values)
        self.conn.commit()

    def insert_incident(self, **kwargs: Any) -> None:
        keys = ",".join(kwargs.keys())
        values = list(kwargs.values())
        placeholders = ",".join(["?"] * len(values))
        self.conn.execute(f"INSERT INTO incidents ({keys}) VALUES ({placeholders})", values)
        self.conn.commit()

    def insert_pnl(self, **kwargs: Any) -> None:
        keys = ",".join(kwargs.keys())
        values = list(kwargs.values())
        placeholders = ",".join(["?"] * len(values))
        self.conn.execute(f"INSERT INTO pnl ({keys}) VALUES ({placeholders})", values)
        self.conn.commit()

    def insert_external_price(self, **kwargs: Any) -> None:
        keys = ",".join(kwargs.keys())
        values = list(kwargs.values())
        placeholders = ",".join(["?"] * len(values))
        self.conn.execute(f"INSERT INTO external_prices ({keys}) VALUES ({placeholders})", values)
        self.conn.commit()

    def insert_correlation(self, **kwargs: Any) -> None:
        keys = ",".join(kwargs.keys())
        values = list(kwargs.values())
        placeholders = ",".join(["?"] * len(values))
        self.conn.execute(f"INSERT INTO correlation_signals ({keys}) VALUES ({placeholders})", values)
        self.conn.commit()

    def fetch_recent(self, table: str, limit: int = 200) -> list[sqlite3.Row]:
        cur = self.conn.cursor()
        cur.execute(f"SELECT * FROM {table} ORDER BY id DESC LIMIT ?", (limit,))
        return cur.fetchall()
