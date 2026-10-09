"""What the bot talks to. Real systems implement these protocols; the synthetic backend is for demos and tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Protocol


@dataclass(frozen=True)
class ServiceStatus:
    service: str
    env: str
    version: str
    healthy: bool
    detail: str = ""


@dataclass(frozen=True)
class Alert:
    name: str
    service: str
    severity: str
    summary: str
    silenced: bool = False


@dataclass(frozen=True)
class DeployRecord:
    service: str
    env: str
    version: str
    by: str
    at: datetime
    ok: bool


class Backend(Protocol):
    def statuses(self, service: str | None) -> list[ServiceStatus]: ...
    def alerts(self) -> list[Alert]: ...
    def silence(self, alert_name: str, duration: timedelta, author: str, reason: str) -> str: ...
    def deploys(self, service: str | None, limit: int) -> list[DeployRecord]: ...
    def deploy(self, service: str, env: str, version: str, by: str, now: datetime) -> str: ...


@dataclass
class SyntheticBackend:
    """In-memory, deterministic, fictional. No network, no real systems."""

    versions: dict[tuple[str, str], str] = field(default_factory=dict)
    unhealthy: set[tuple[str, str]] = field(default_factory=set)
    firing: list[Alert] = field(default_factory=list)
    silences: list[tuple[str, timedelta, str, str]] = field(default_factory=list)
    history: list[DeployRecord] = field(default_factory=list)

    @classmethod
    def demo(cls, now: datetime) -> SyntheticBackend:
        b = cls()
        for svc, ver in (("orders-api", "a1b2c3d4"), ("billing-worker", "9f8e7d6c")):
            for env in ("dev", "stage", "prod"):
                b.versions[(svc, env)] = ver
                b.history.append(DeployRecord(svc, env, ver, "ci-bot", now - timedelta(hours=26), True))
        b.versions[("orders-api", "dev")] = "ffee0011"
        b.history.append(DeployRecord("orders-api", "dev", "ffee0011", "alice", now - timedelta(hours=2), True))
        b.unhealthy.add(("billing-worker", "stage"))
        b.firing = [
            Alert("HighErrorRate", "billing-worker", "critical", "5xx above 5% for 10m (stage)"),
            Alert("DiskAlmostFull", "orders-api", "warning", "/var at 91% on node-3 (dev)"),
        ]
        return b

    def statuses(self, service: str | None) -> list[ServiceStatus]:
        return [
            ServiceStatus(
                s, e, v, (s, e) not in self.unhealthy, "" if (s, e) not in self.unhealthy else "failing probes"
            )
            for (s, e), v in sorted(self.versions.items())
            if service in (None, s)
        ]

    def alerts(self) -> list[Alert]:
        muted = {s[0] for s in self.silences}
        return [Alert(a.name, a.service, a.severity, a.summary, a.name in muted) for a in self.firing]

    def silence(self, alert_name: str, duration: timedelta, author: str, reason: str) -> str:
        self.silences.append((alert_name, duration, author, reason))
        return f"silence-{len(self.silences):03d}"

    def deploys(self, service: str | None, limit: int) -> list[DeployRecord]:
        rows = [d for d in self.history if service in (None, d.service)]
        return sorted(rows, key=lambda d: d.at, reverse=True)[:limit]

    def deploy(self, service: str, env: str, version: str, by: str, now: datetime) -> str:
        self.versions[(service, env)] = version
        self.history.append(DeployRecord(service, env, version, by, now, True))
        return f"{service} {env} now runs {version}"
