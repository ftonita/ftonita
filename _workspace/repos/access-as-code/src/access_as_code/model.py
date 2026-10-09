"""Typed view of a schema-valid access.yml, with group resolution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import yaml

from .schemas import schema_errors


class AccessFileError(ValueError):
    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


@dataclass(frozen=True)
class Role:
    name: str
    vault: tuple[str, ...] = ()
    kubernetes: str | None = None
    gitlab: str | None = None

    @property
    def elevated(self) -> bool:
        return "delete" in self.vault or "sudo" in self.vault or self.kubernetes == "admin"


@dataclass(frozen=True)
class Person:
    id: str
    team: str
    active: bool


@dataclass(frozen=True)
class Grant:
    index: int
    subject: str
    role: str
    team: str
    env: str
    expires: date | None = None
    ticket: str | None = None
    reason: str | None = None

    @property
    def is_group(self) -> bool:
        return self.subject.startswith("group:")

    @property
    def subject_name(self) -> str:
        return self.subject.removeprefix("group:")

    def describe(self) -> str:
        return f"grant #{self.index} ({self.subject} -> {self.role} on {self.team}/{self.env})"


@dataclass(frozen=True)
class Access:
    teams: tuple[str, ...]
    environments: tuple[str, ...]
    production: tuple[str, ...]
    roles: dict[str, Role]
    people: dict[str, Person]
    groups: dict[str, tuple[str, ...]]
    grants: tuple[Grant, ...]

    def members(self, grant: Grant) -> tuple[str, ...]:
        """People a grant applies to (unknown subjects resolve to nobody)."""
        if grant.is_group:
            return self.groups.get(grant.subject_name, ())
        return (grant.subject_name,) if grant.subject_name in self.people else ()


def parse(doc: Any) -> Access:
    problems = schema_errors(doc)
    if problems:
        raise AccessFileError(problems)
    roles = {
        n: Role(n, tuple(r.get("vault", ())), r.get("kubernetes"), r.get("gitlab"))
        for n, r in doc["roles"].items()
    }
    people = {n: Person(n, p["team"], p["status"] == "active") for n, p in doc["people"].items()}
    grants = tuple(
        Grant(
            i,
            g["subject"],
            g["role"],
            g["team"],
            g["env"],
            date.fromisoformat(g["expires"]) if "expires" in g else None,
            g.get("ticket"),
            g.get("reason"),
        )
        for i, g in enumerate(doc["grants"])
    )
    return Access(
        tuple(doc["teams"]),
        tuple(doc["environments"]),
        tuple(doc.get("production_environments", ["prod"])),
        roles,
        people,
        {k: tuple(v) for k, v in doc.get("groups", {}).items()},
        grants,
    )


class _Loader(yaml.SafeLoader):
    """SafeLoader that keeps `2026-12-01` a string (validated by the schema) instead of a date object."""


_Loader.yaml_implicit_resolvers = {
    k: [(tag, rx) for tag, rx in v if tag != "tag:yaml.org,2002:timestamp"]
    for k, v in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def load(path: str) -> Access:
    try:
        with open(path, encoding="utf-8") as fh:
            doc = yaml.load(fh, Loader=_Loader)  # noqa: S506 - restricted SafeLoader subclass
    except (OSError, yaml.YAMLError) as exc:
        raise AccessFileError([f"cannot read {path}: {exc}"]) from exc
    try:
        return parse(doc)
    except ValueError as exc:  # bad date etc.
        if isinstance(exc, AccessFileError):
            raise
        raise AccessFileError([str(exc)]) from exc
