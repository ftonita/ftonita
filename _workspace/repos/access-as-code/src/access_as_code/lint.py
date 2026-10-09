"""Least-privilege rules. Each rule has a stable id so exceptions and docs can reference it."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from .model import Access

MAX_PERSON_PROD_DAYS = 90
MAX_ELEVATED_PROD_DAYS = 7
SOON_DAYS = 14


@dataclass(frozen=True)
class Violation:
    rule: str
    severity: str  # error | warning | info
    message: str

    def __str__(self) -> str:
        return f"{self.rule} {self.severity}: {self.message}"


RULES = {
    "AAC001": "No role may hold the Vault `sudo` capability.",
    "AAC002": "Grants must reference known teams, environments, roles and subjects.",
    "AAC003": "Production grants need a ticket; direct person grants also need an expiry (max 90 days).",
    "AAC004": "Elevated roles (delete / k8s admin) in production need a ticket and expire within 7 days.",
    "AAC005": "Offboarded people must hold no access, directly or through a group.",
    "AAC006": "Expired grants must be removed.",
    "AAC007": "Separation of duties: nobody is both `deployer` and `approver` on one team in production.",
    "AAC008": "Cross-team access needs a ticket.",
    "AAC009": "Duplicate grants.",
    "AAC010": "Unused roles and groups.",
    "AAC011": "Grants expiring within 14 days are due for review.",
}


def lint(acc: Access, today: date) -> list[Violation]:
    out: list[Violation] = []

    def add(rule: str, sev: str, msg: str) -> None:
        out.append(Violation(rule, sev, msg))

    for role in acc.roles.values():
        if "sudo" in role.vault:
            add("AAC001", "error", f"role '{role.name}' grants the Vault 'sudo' capability")

    seen: dict[tuple, int] = {}
    used_roles: set[str] = set()
    used_groups: set[str] = set()
    prod_roles: dict[tuple[str, str], set[str]] = defaultdict(set)  # (person, team) -> roles on prod

    for g in acc.grants:
        d = g.describe()
        valid = True
        if g.team not in acc.teams:
            add("AAC002", "error", f"{d}: unknown team '{g.team}'")
            valid = False
        if g.env not in acc.environments:
            add("AAC002", "error", f"{d}: unknown environment '{g.env}'")
            valid = False
        if g.role not in acc.roles:
            add("AAC002", "error", f"{d}: unknown role '{g.role}'")
            valid = False
        known = g.subject_name in (acc.groups if g.is_group else acc.people)
        if not known:
            add("AAC002", "error", f"{d}: unknown subject '{g.subject}'")
            valid = False
        used_roles.add(g.role)
        if g.is_group:
            used_groups.add(g.subject_name)
        if not valid:
            continue

        key = (g.subject, g.role, g.team, g.env)
        if key in seen:
            add("AAC009", "warning", f"{d} duplicates grant #{seen[key]}")
        seen.setdefault(key, g.index)

        role, prod = acc.roles[g.role], g.env in acc.production
        if prod:
            if not g.ticket:
                add("AAC003", "error", f"{d}: production grant without a ticket")
            if not g.is_group:
                if g.expires is None:
                    add("AAC003", "error", f"{d}: direct production grant without an expiry")
                elif g.expires > today + timedelta(days=MAX_PERSON_PROD_DAYS):
                    add("AAC003", "error", f"{d}: expiry is more than {MAX_PERSON_PROD_DAYS} days away")
            if role.elevated:
                if (
                    not g.ticket
                    or g.expires is None
                    or g.expires > today + timedelta(days=MAX_ELEVATED_PROD_DAYS)
                ):
                    add(
                        "AAC004",
                        "error",
                        f"{d}: elevated role '{role.name}' in production needs a ticket "
                        f"and an expiry within {MAX_ELEVATED_PROD_DAYS} days",
                    )
        if g.expires is not None:
            if g.expires < today:
                add("AAC006", "error", f"{d}: expired on {g.expires}")
            elif g.expires <= today + timedelta(days=SOON_DAYS):
                add("AAC011", "warning", f"{d}: expires on {g.expires}")

        for pid in acc.members(g):
            person = acc.people[pid]
            if not person.active:
                add("AAC005", "error", f"{d}: '{pid}' is offboarded")
            if person.team != g.team and not g.ticket:
                add("AAC008", "warning", f"{d}: '{pid}' belongs to team '{person.team}' (no ticket)")
            if prod:
                prod_roles[(pid, g.team)].add(g.role)

    for (pid, team), roles in sorted(prod_roles.items()):
        if {"deployer", "approver"} <= roles:
            add("AAC007", "error", f"'{pid}' is both deployer and approver on {team}/prod")

    for name in sorted(set(acc.roles) - used_roles):
        add("AAC010", "info", f"role '{name}' is never granted")
    for name in sorted(set(acc.groups) - used_groups):
        add("AAC010", "info", f"group '{name}' is never granted")
    order = {"error": 0, "warning": 1, "info": 2}
    return sorted(out, key=lambda v: (order[v.severity], v.rule, v.message))
