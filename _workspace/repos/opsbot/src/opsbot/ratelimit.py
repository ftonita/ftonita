"""Token bucket per user with an injected clock."""

from __future__ import annotations

from datetime import datetime


class RateLimiter:
    def __init__(self, burst: int, per_minute: int) -> None:
        self.burst, self.rate = burst, per_minute / 60.0
        self._state: dict[int, tuple[float, datetime]] = {}

    def allow(self, user_id: int, now: datetime) -> bool:
        tokens, last = self._state.get(user_id, (float(self.burst), now))
        tokens = min(self.burst, tokens + (now - last).total_seconds() * self.rate)
        if tokens < 1:
            self._state[user_id] = (tokens, now)
            return False
        self._state[user_id] = (tokens - 1, now)
        return True
