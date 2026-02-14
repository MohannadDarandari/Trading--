from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass


@dataclass
class SpotPoint:
    ts: float
    price: float


class SpotFeatureBuffer:
    def __init__(self, max_age_sec: int = 120) -> None:
        self.max_age = max_age_sec
        self.points: deque[SpotPoint] = deque()

    def add(self, price: float) -> None:
        now = time.time()
        self.points.append(SpotPoint(now, price))
        while self.points and now - self.points[0].ts > self.max_age:
            self.points.popleft()

    def _price_at(self, seconds_ago: int) -> float | None:
        target = time.time() - seconds_ago
        for p in reversed(self.points):
            if p.ts <= target:
                return p.price
        return None

    def returns(self) -> tuple[float | None, float | None]:
        p_15 = self._price_at(15)
        p_60 = self._price_at(60)
        latest = self.points[-1].price if self.points else None
        if latest is None or p_15 is None or p_60 is None:
            return None, None
        return (latest - p_15) / p_15, (latest - p_60) / p_60

    def realized_vol(self) -> float | None:
        if len(self.points) < 3:
            return None
        returns = []
        for i in range(1, len(self.points)):
            r = (self.points[i].price - self.points[i - 1].price) / self.points[i - 1].price
            returns.append(r)
        if not returns:
            return None
        return (sum(r * r for r in returns) / len(returns)) ** 0.5


def lag_detector(spot_move_30s: float, pm_move_30s: float, threshold: float = 0.002) -> tuple[bool, float]:
    """Return (lag_flag, score)."""
    lag = abs(spot_move_30s) >= threshold and abs(pm_move_30s) < (threshold / 2)
    score = abs(spot_move_30s) * (1.0 + abs(pm_move_30s))
    return lag, score
