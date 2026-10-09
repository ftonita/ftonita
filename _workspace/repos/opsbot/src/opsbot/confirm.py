"""Pending actions that need an explicit /confirm, optionally by a second person."""

from __future__ import annotations

import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no look-alike characters


@dataclass(frozen=True)
class Pending:
    code: str
    requester_id: int
    description: str
    action: Callable[[], str]
    expires: datetime
    needs_other: bool  # four-eyes: confirmer must be an approver and not the requester


class Confirmations:
    def __init__(self, ttl_seconds: int, rng: Callable[[int], str] | None = None) -> None:
        self.ttl = timedelta(seconds=ttl_seconds)
        self._items: dict[str, Pending] = {}
        self._rng = rng or (lambda n: "".join(secrets.choice(ALPHABET) for _ in range(n)))

    def create(
        self, requester_id: int, description: str, action: Callable[[], str], now: datetime, needs_other: bool
    ) -> Pending:
        self._purge(now)
        code = self._rng(6)
        while code in self._items:
            code = self._rng(6)
        p = Pending(code, requester_id, description, action, now + self.ttl, needs_other)
        self._items[code] = p
        return p

    def take(self, code: str, now: datetime) -> Pending | None:
        """Single use: returns the pending action and forgets it, or None if unknown/expired."""
        self._purge(now)
        return self._items.pop(code.upper(), None)

    def peek(self, code: str, now: datetime) -> Pending | None:
        self._purge(now)
        return self._items.get(code.upper())

    def _purge(self, now: datetime) -> None:
        for code in [c for c, p in self._items.items() if p.expires <= now]:
            del self._items[code]

    def __len__(self) -> int:
        return len(self._items)
