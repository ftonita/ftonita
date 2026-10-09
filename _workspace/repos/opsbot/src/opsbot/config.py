"""Configuration. Secrets (the bot token) come from the environment, never from this file."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import yaml

ROLES = ("viewer", "operator", "approver", "admin")


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class User:
    id: int
    name: str
    role: str

    def at_least(self, role: str) -> bool:
        return ROLES.index(self.role) >= ROLES.index(role)


@dataclass(frozen=True)
class Config:
    users: dict[int, User]
    services: tuple[str, ...]
    environments: tuple[str, ...]
    prod_environments: tuple[str, ...] = ("prod",)
    rate_burst: int = 5
    rate_per_minute: int = 20
    confirm_ttl_seconds: int = 120
    max_silence_hours: int = 8
    allowed_chats: tuple[int, ...] = field(default_factory=tuple)  # empty = private chats only


def parse_config(raw: Any) -> Config:
    if not isinstance(raw, dict):
        raise ConfigError("config must be a mapping")
    unknown = set(raw) - {
        "users",
        "services",
        "environments",
        "prod_environments",
        "rate_limit",
        "confirm_ttl_seconds",
        "max_silence_hours",
        "allowed_chats",
    }
    if unknown:
        raise ConfigError(f"unknown keys: {', '.join(sorted(unknown))}")
    users: dict[int, User] = {}
    for u in raw.get("users", []):
        if not isinstance(u, dict) or not isinstance(u.get("id"), int) or u.get("role") not in ROLES:
            raise ConfigError(f"invalid user entry (need int id and role in {ROLES}): {u!r}")
        if u["id"] in users:
            raise ConfigError(f"duplicate user id {u['id']}")
        users[u["id"]] = User(u["id"], str(u.get("name") or u["id"]), u["role"])
    if not users:
        raise ConfigError("at least one user is required")
    services, envs = tuple(raw.get("services", ())), tuple(raw.get("environments", ()))
    if not services or not envs:
        raise ConfigError("'services' and 'environments' must be non-empty")
    prod = tuple(raw.get("prod_environments", ("prod",)))
    if not set(prod) <= set(envs):
        raise ConfigError("prod_environments must be a subset of environments")
    rl = raw.get("rate_limit", {})
    cfg = Config(
        users,
        services,
        envs,
        prod,
        int(rl.get("burst", 5)),
        int(rl.get("per_minute", 20)),
        int(raw.get("confirm_ttl_seconds", 120)),
        int(raw.get("max_silence_hours", 8)),
        tuple(raw.get("allowed_chats", ())),
    )
    if min(cfg.rate_burst, cfg.rate_per_minute, cfg.confirm_ttl_seconds, cfg.max_silence_hours) < 1:
        raise ConfigError("numeric limits must be >= 1")
    return cfg


def load_config(path: str) -> Config:
    try:
        with open(path, encoding="utf-8") as fh:
            return parse_config(yaml.safe_load(fh))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"cannot read {path}: {exc}") from exc
