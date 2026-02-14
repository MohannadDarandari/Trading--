from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class RiskLimits:
    max_open_exposure_pct: float
    max_trades_per_hour: int
    daily_stop_loss_pct: float
    partial_fill_streak_kill: int
    partial_fill_day_kill: int
    api_error_kill_10m: int
    latency_kill_ms: float
    latency_kill_window_sec: int
    thin_book_kill_scans: int


class RiskManager:
    def __init__(self, limits: RiskLimits) -> None:
        self.limits = limits
        self.partial_fill_streak = 0
        self.partial_fill_day = 0
        self.api_errors_10m = []
        self.latency_window = []
        self.thin_book_streak = 0
        self.trades_last_hour = []
        self.kill_reason = ""
        self.current_open_exposure = 0.0

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
        self.latency_window = [(t, v) for t, v in self.latency_window if now - t <= self.limits.latency_kill_window_sec]

    def record_thin_book(self, thin: bool) -> None:
        if thin:
            self.thin_book_streak += 1
        else:
            self.thin_book_streak = 0

    def record_trade(self) -> None:
        now = time.time()
        self.trades_last_hour.append(now)
        self.trades_last_hour = [t for t in self.trades_last_hour if now - t <= 3600]

    def can_take_trade(self, bankroll: float, exposure_add: float) -> bool:
        if bankroll <= 0:
            return False
        projected = self.current_open_exposure + exposure_add
        return projected <= bankroll * self.limits.max_open_exposure_pct

    def add_exposure(self, exposure: float) -> None:
        self.current_open_exposure += exposure

    def reduce_exposure(self, exposure: float) -> None:
        self.current_open_exposure = max(0.0, self.current_open_exposure - exposure)

    def should_kill(self) -> bool:
        if self.partial_fill_streak >= self.limits.partial_fill_streak_kill:
            self.kill_reason = "partial_fill_streak"
            return True
        if self.partial_fill_day >= self.limits.partial_fill_day_kill:
            self.kill_reason = "partial_fill_day"
            return True
        if len(self.api_errors_10m) >= self.limits.api_error_kill_10m:
            self.kill_reason = "api_errors"
            return True
        if self.thin_book_streak >= self.limits.thin_book_kill_scans:
            self.kill_reason = "thin_book_streak"
            return True
        if self.latency_window:
            avg_latency = sum(v for _, v in self.latency_window) / len(self.latency_window)
            if avg_latency >= self.limits.latency_kill_ms:
                self.kill_reason = "latency"
                return True
        if len(self.trades_last_hour) >= self.limits.max_trades_per_hour:
            self.kill_reason = "max_trades_per_hour"
            return True
        return False
