from __future__ import annotations

import itertools
from datetime import datetime, timedelta, timezone

import pytest

from opsbot.audit import AuditLog
from opsbot.backends import SyntheticBackend
from opsbot.config import parse_config
from opsbot.core import OpsBot

NOW = datetime(2026, 10, 9, 10, 0, tzinfo=timezone.utc)

RAW = {
    "users": [
        {"id": 1, "name": "alice", "role": "operator"},
        {"id": 2, "name": "bob", "role": "approver"},
        {"id": 3, "name": "carol", "role": "viewer"},
        {"id": 4, "name": "dave", "role": "admin"},
        {"id": 5, "name": "erin", "role": "operator"},
    ],
    "services": ["orders-api", "billing-worker"],
    "environments": ["dev", "stage", "prod"],
    "prod_environments": ["prod"],
    "rate_limit": {"burst": 5, "per_minute": 20},
    "confirm_ttl_seconds": 120,
    "max_silence_hours": 8,
}


class Clock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


@pytest.fixture
def cfg():
    return parse_config(RAW)


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def backend():
    return SyntheticBackend.demo(NOW)


@pytest.fixture
def audit():
    return AuditLog()


@pytest.fixture
def bot(cfg, backend, audit, clock):
    codes = itertools.cycle(["AAAAAA", "BBBBBB", "CCCCCC", "DDDDDD"])
    return OpsBot(cfg, backend, audit, clock, lambda n: next(codes))
