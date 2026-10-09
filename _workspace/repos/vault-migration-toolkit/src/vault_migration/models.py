"""Data model. Secret values are wrapped so they cannot leak through repr, logs or f-strings."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


class Secret:
    """Holds a value; str()/repr() are always redacted. Call .reveal() deliberately."""

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        self._value = value

    def reveal(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return "Secret(<redacted>)"

    __str__ = __repr__

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Secret) and self._value == other._value

    def __hash__(self) -> int:
        return hash(self._value)


@dataclass(frozen=True)
class LegacySecret:
    id: str
    name: str
    app: str
    env: str
    team: str
    kind: str
    value: Secret = field(repr=False)
    last_rotated: date | None = None
    consumers: tuple[str, ...] = ()


@dataclass(frozen=True)
class Target:
    mount: str
    path: str

    def __str__(self) -> str:
        return f"{self.mount}/{self.path}"


@dataclass(frozen=True)
class PlanItem:
    secret_id: str
    target: Target


@dataclass(frozen=True)
class Unmapped:
    secret_id: str
    reason: str
