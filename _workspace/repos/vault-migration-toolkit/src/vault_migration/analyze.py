"""Inventory findings. Reports never contain secret values."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from .fingerprint import fingerprint
from .models import LegacySecret

COMMON = {"password", "passw0rd", "changeme", "admin", "admin123", "secret", "qwerty", "123456", "letmein"}


@dataclass(frozen=True)
class Finding:
    severity: str  # "high" | "medium" | "low"
    kind: str  # weak | shared_across_envs | duplicate | stale | unowned
    secret_ids: tuple[str, ...]
    detail: str


def is_weak(value: str) -> bool:
    return len(value) < 12 or value.lower() in COMMON or len(set(value)) < 5


def analyze(secrets: list[LegacySecret], key: bytes, today: date, stale_days: int = 365) -> list[Finding]:
    findings: list[Finding] = []
    by_fp: dict[str, list[LegacySecret]] = defaultdict(list)
    for s in secrets:
        by_fp[fingerprint(key, s.value)].append(s)
        if is_weak(s.value.reveal()):
            sev = "high" if s.env.lower() in ("prod", "production") else "medium"
            findings.append(
                Finding(sev, "weak", (s.id,), f"{s.name} ({s.app}/{s.env}): too short, common or low entropy")
            )
        if not s.team:
            findings.append(Finding("low", "unowned", (s.id,), f"{s.name} ({s.app}/{s.env}): no owning team"))
        if s.last_rotated is None:
            findings.append(Finding("medium", "stale", (s.id,), f"{s.name}: never rotated or unknown"))
        elif (today - s.last_rotated).days > stale_days:
            age = (today - s.last_rotated).days
            findings.append(Finding("medium", "stale", (s.id,), f"{s.name}: last rotated {age} days ago"))
    for group in by_fp.values():
        if len(group) < 2:
            continue
        ids = tuple(sorted(g.id for g in group))
        envs = {g.env.lower() for g in group}
        names = ", ".join(sorted(f"{g.app}/{g.env}/{g.name}" for g in group))
        if len(envs) > 1:
            sev = "high" if envs & {"prod", "production"} else "medium"
            findings.append(Finding(sev, "shared_across_envs", ids, f"same value in {names}"))
        else:
            findings.append(Finding("low", "duplicate", ids, f"same value in {names}"))
    order = {"high": 0, "medium": 1, "low": 2}
    return sorted(findings, key=lambda f: (order[f.severity], f.kind, f.secret_ids))
