"""Mapping rules: how legacy (team, env, app, name) become a Vault mount and path."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import yaml

from .models import LegacySecret, PlanItem, Target, Unmapped

_SAFE = re.compile(r"[^a-z0-9._-]+")


def slug(value: str) -> str:
    return _SAFE.sub("-", value.strip().lower()).strip("-")


@dataclass(frozen=True)
class Rules:
    mount_prefix: str = "kv-"
    allowed_envs: tuple[str, ...] = ("dev", "stage", "prod")
    team_aliases: dict[str, str] = field(default_factory=dict)
    env_aliases: dict[str, str] = field(default_factory=dict)
    app_owners: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_file(cls, path: str) -> Rules:
        with open(path, encoding="utf-8") as fh:
            return cls.from_dict(yaml.safe_load(fh) or {})

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Rules:
        unknown = set(raw) - {"mount_prefix", "allowed_envs", "team_aliases", "env_aliases", "app_owners"}
        if unknown:
            raise ValueError(f"unknown rule keys: {', '.join(sorted(unknown))}")
        return cls(
            mount_prefix=raw.get("mount_prefix", "kv-"),
            allowed_envs=tuple(raw.get("allowed_envs", ("dev", "stage", "prod"))),
            team_aliases={slug(k): slug(v) for k, v in raw.get("team_aliases", {}).items()},
            env_aliases={slug(k): slug(v) for k, v in raw.get("env_aliases", {}).items()},
            app_owners={slug(k): slug(v) for k, v in raw.get("app_owners", {}).items()},
        )

    def resolve_team(self, s: LegacySecret) -> str:
        team = slug(s.team)
        team = self.team_aliases.get(team, team)
        return team or self.app_owners.get(slug(s.app), "")

    def resolve_env(self, s: LegacySecret) -> str:
        env = slug(s.env)
        return self.env_aliases.get(env, env)


def plan(secrets: list[LegacySecret], rules: Rules) -> tuple[list[PlanItem], list[Unmapped]]:
    """Deterministic mapping. Anything ambiguous goes to a manual queue instead of being guessed."""
    items: list[PlanItem] = []
    unmapped: list[Unmapped] = []
    seen: dict[Target, str] = {}
    for s in sorted(secrets, key=lambda x: x.id):
        team, env, app, name = rules.resolve_team(s), rules.resolve_env(s), slug(s.app), slug(s.name)
        if not team:
            unmapped.append(Unmapped(s.id, "no owning team (and app has no owner in rules)"))
        elif env not in rules.allowed_envs:
            unmapped.append(Unmapped(s.id, f"environment {s.env!r} is not one of {list(rules.allowed_envs)}"))
        elif not app or not name:
            unmapped.append(Unmapped(s.id, "missing app or name"))
        else:
            target = Target(f"{rules.mount_prefix}{team}", f"{env}/{app}/{name}")
            if target in seen:
                unmapped.append(Unmapped(s.id, f"target {target} already taken by {seen[target]}"))
                continue
            seen[target] = s.id
            items.append(PlanItem(s.id, target))
    return items, unmapped
