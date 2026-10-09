"""Deterministic SYNTHETIC legacy export for demos and tests. Every value is fake by construction."""

from __future__ import annotations

import json
import random
from pathlib import Path

RULES_YAML = """\
# Mapping rules for the synthetic demo.
mount_prefix: kv-
allowed_envs: [dev, stage, prod]
team_aliases:
  "Payments Team": payments
  scoring-team: scoring
env_aliases:
  production: prod
  staging: stage
  development: dev
app_owners:          # fallback when the legacy record has no team
  reports: platform
  gateway: platform
"""

TEAMS_APPS = {"payments": ["orders", "ledger"], "scoring": ["scorer"], "platform": ["gateway", "reports"]}
KINDS = ["db_password", "api_key", "token"]


def _fake(rng: random.Random, tag: str) -> str:
    return f"SYNTHETIC-{tag}-{rng.getrandbits(96):024x}"


def build_records(seed: int = 7) -> list[dict[str, str]]:
    rng = random.Random(seed)
    rows: list[dict[str, str]] = []
    n = 0

    def add(**kw: str) -> None:
        nonlocal n
        n += 1
        rows.append({"id": f"S{n:03d}", "kind": "password", "consumers": "", **kw})

    for team, apps in TEAMS_APPS.items():
        for app in apps:
            for env in ("dev", "stage", "prod"):
                for kind in KINDS[:2]:
                    add(
                        name=kind,
                        app=app,
                        env=env,
                        team=team,
                        kind=kind,
                        value=_fake(rng, kind),
                        last_rotated=f"2026-0{rng.randint(3, 9)}-1{rng.randint(0, 9)}",
                        consumers=f"{app}-svc",
                    )
    # problems the toolkit must surface
    add(
        name="admin_password",
        app="orders",
        env="prod",
        team="payments",
        value="changeme",
        last_rotated="2024-01-05",
    )
    add(
        name="legacy_pin", app="ledger", env="stage", team="payments", value="Ab1!", last_rotated="2025-02-02"
    )
    shared = _fake(rng, "shared")
    add(
        name="smtp_password",
        app="orders",
        env="stage",
        team="payments",
        value=shared,
        last_rotated="2026-01-10",
    )
    add(
        name="smtp_password",
        app="orders",
        env="prod",
        team="payments",
        value=shared,
        last_rotated="2026-01-10",
    )
    add(
        name="jwt_secret",
        app="scorer",
        env="production",
        team="Payments Team",
        value=_fake(rng, "jwt"),
        last_rotated="2023-06-01",
    )
    add(
        name="s3_key",
        app="reports",
        env="staging",
        team="",
        value=_fake(rng, "s3"),
        last_rotated="2026-04-04",
    )
    add(name="old_token", app="mystery", env="prod", team="", value=_fake(rng, "old"))
    add(
        name="uat_db",
        app="orders",
        env="uat",
        team="payments",
        value=_fake(rng, "uat"),
        last_rotated="2026-05-05",
    )
    return rows


def write_demo(out: str | Path, seed: int = 7) -> tuple[Path, Path]:
    d = Path(out)
    d.mkdir(parents=True, exist_ok=True)
    legacy, rules = d / "legacy.json", d / "rules.yml"
    legacy.write_text(json.dumps(build_records(seed), indent=2), encoding="utf-8")
    rules.write_text(RULES_YAML, encoding="utf-8")
    return legacy, rules
