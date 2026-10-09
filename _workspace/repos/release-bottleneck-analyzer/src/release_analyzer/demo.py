"""Deterministic SYNTHETIC datasets. 'before' has a release train and slow reviews; 'after' deploys on merge.

The numbers are properties of this generator, not measurements of any real organisation."""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

START = datetime(2026, 3, 2, 9, 0, tzinfo=timezone.utc)  # a Monday
WEEKS = 12
TEAMS = ("payments", "scoring", "platform")
SCENARIOS = {
    "before": {
        "review_wait_h": 10.0,
        "review_h": 5.0,
        "merge_wait_h": 3.0,
        "ci_min": 28,
        "train_days": 7,
        "failure": 0.18,
        "restore_h": 20.0,
    },
    "after": {
        "review_wait_h": 2.5,
        "review_h": 3.0,
        "merge_wait_h": 0.5,
        "ci_min": 12,
        "train_days": 0,
        "failure": 0.07,
        "restore_h": 2.0,
    },
}


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _working_start(rng: random.Random) -> datetime:
    day = START + timedelta(days=rng.randrange(WEEKS * 7))
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day.replace(hour=rng.randint(9, 17), minute=rng.randrange(60))


def _trains(days: int) -> list[datetime]:
    t, out = START + timedelta(days=3, hours=5), []  # Thursday 14:00
    while t < START + timedelta(days=WEEKS * 7 + 60):
        out.append(t)
        t += timedelta(days=days)
    return out


def build(scenario: str, seed: int = 11, n: int = 120) -> list[dict]:
    p = SCENARIOS[scenario]
    rng = random.Random(f"{scenario}-{seed}")
    trains = _trains(p["train_days"]) if p["train_days"] else []
    rows = []
    for i in range(n):
        created = _working_start(rng)
        size = int(rng.lognormvariate(4.6, 0.9))
        size_factor = 1 + min(size, 800) / 400
        first = created + timedelta(hours=rng.lognormvariate(0, 0.6) * p["review_wait_h"])
        approved = first + timedelta(hours=rng.lognormvariate(0, 0.6) * p["review_h"] * size_factor)
        merged = approved + timedelta(hours=rng.lognormvariate(0, 0.5) * p["merge_wait_h"])
        if trains:
            deployed = next(t for t in trains if t > merged)
            release_id = f"R{deployed:%Y%m%d}"
        else:
            deployed = merged + timedelta(minutes=rng.randint(10, 40))
            release_id = ""
        failed = rng.random() < p["failure"]
        rows.append(
            {
                "id": f"MR-{i + 1:03d}",
                "team": rng.choice(TEAMS),
                "size": size,
                "created_at": _iso(created),
                "first_review_at": _iso(first),
                "approved_at": _iso(approved),
                "merged_at": _iso(merged),
                "pipeline_seconds": int(p["ci_min"] * 60 * rng.uniform(0.7, 1.6)),
                "deployed_at": _iso(deployed),
                "release_id": release_id,
                "failed": failed,
                "restored_at": _iso(deployed + timedelta(hours=rng.lognormvariate(0, 0.5) * p["restore_h"]))
                if failed
                else "",
            }
        )
    # a few still in flight, like any real export
    for r in rows[-3:]:
        r["deployed_at"], r["release_id"] = "", ""
    return rows


def write_demo(out: str | Path, seed: int = 11) -> list[Path]:
    d = Path(out)
    d.mkdir(parents=True, exist_ok=True)
    paths = []
    for name in SCENARIOS:
        path = d / f"{name}.json"
        path.write_text(json.dumps(build(name, seed), indent=1), encoding="utf-8")
        paths.append(path)
    return paths
