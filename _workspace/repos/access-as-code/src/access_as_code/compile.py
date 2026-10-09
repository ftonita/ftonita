"""Compile the declaration to what systems enforce. Output is *effective access as of today*:
expired grants, offboarded people and invalid grants never reach the output, even if lint was skipped."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from .model import Access, Grant

GITLAB_ORDER = {"reporter": 1, "developer": 2, "maintainer": 3}
K8S_ORDER = {"view": 1, "edit": 2, "admin": 3}


def effective(acc: Access, today: date) -> list[tuple[Grant, str]]:
    """(grant, person) pairs that are really in force."""
    out = []
    for g in acc.grants:
        if g.team not in acc.teams or g.env not in acc.environments or g.role not in acc.roles:
            continue
        if g.expires is not None and g.expires < today:
            continue
        for pid in acc.members(g):
            if acc.people[pid].active:
                out.append((g, pid))
    return out


def policy_hcl(team: str, env: str, caps: tuple[str, ...]) -> str:
    lines = []
    data = [c for c in ("create", "read", "update", "delete") if c in caps]
    meta = [c for c in ("list", "read") if c in caps]
    if data:
        lines.append(f'path "kv-{team}/data/{env}/*" {{\n  capabilities = {json.dumps(data)}\n}}')
    if meta:
        lines.append(f'path "kv-{team}/metadata/{env}/*" {{\n  capabilities = {json.dumps(meta)}\n}}')
    return "\n\n".join(lines) + "\n"


@dataclass(frozen=True)
class Artifacts:
    vault_policies: dict[str, str]
    vault_groups: dict[str, list[str]]
    kubernetes: dict[str, list[str]]  # "<ns>/<level>" -> members
    gitlab: dict[str, dict[str, str]]  # team -> {person: level}

    def as_state(self) -> dict[str, Any]:
        return {
            "vault_policies": self.vault_policies,
            "vault_groups": self.vault_groups,
            "kubernetes": self.kubernetes,
            "gitlab": self.gitlab,
        }


def compile_access(acc: Access, today: date) -> Artifacts:
    policies: dict[str, str] = {}
    groups: dict[str, set[str]] = {}
    k8s: dict[str, set[str]] = {}
    gitlab: dict[str, dict[str, str]] = {}
    for g, pid in effective(acc, today):
        role = acc.roles[g.role]
        if role.vault:
            name = f"{g.team}-{g.env}-{role.name}"
            policies[name] = policy_hcl(g.team, g.env, role.vault)
            groups.setdefault(name, set()).add(pid)
        if role.kubernetes:
            k8s.setdefault(f"{g.team}-{g.env}/{role.kubernetes}", set()).add(pid)
        if role.gitlab:
            cur = gitlab.setdefault(g.team, {}).get(pid)
            if cur is None or GITLAB_ORDER[role.gitlab] > GITLAB_ORDER[cur]:
                gitlab[g.team][pid] = role.gitlab
    return Artifacts(
        dict(sorted(policies.items())),
        {k: sorted(v) for k, v in sorted(groups.items())},
        {k: sorted(v) for k, v in sorted(k8s.items())},
        {t: dict(sorted(m.items())) for t, m in sorted(gitlab.items())},
    )


def rolebinding(key: str, members: list[str]) -> dict[str, Any]:
    ns, level = key.split("/")
    return {
        "apiVersion": "rbac.authorization.k8s.io/v1",
        "kind": "RoleBinding",
        "metadata": {"name": f"aac-{level}", "namespace": ns, "labels": {"managed-by": "access-as-code"}},
        "roleRef": {"apiGroup": "rbac.authorization.k8s.io", "kind": "ClusterRole", "name": level},
        "subjects": [{"apiGroup": "rbac.authorization.k8s.io", "kind": "User", "name": m} for m in members],
    }


def write(art: Artifacts, out: str | Path) -> list[Path]:
    root = Path(out)
    written: list[Path] = []

    def put(rel: str, text: str) -> None:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        written.append(p)

    for name, hcl in art.vault_policies.items():
        put(f"vault/policies/{name}.hcl", hcl)
    put(
        "vault/groups.json",
        json.dumps({n: {"policies": [n], "members": m} for n, m in art.vault_groups.items()}, indent=2)
        + "\n",
    )
    for key, members in art.kubernetes.items():
        put(
            f"kubernetes/{key.replace('/', '--')}.yaml",
            yaml.safe_dump(rolebinding(key, members), sort_keys=False),
        )
    put("gitlab/members.json", json.dumps(art.gitlab, indent=2) + "\n")
    return written
