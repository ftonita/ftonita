from __future__ import annotations

import copy
from datetime import date
from pathlib import Path

import pytest

from access_as_code.model import load, parse

ROOT = Path(__file__).resolve().parent.parent
GOOD = ROOT / "examples" / "access.yml"
BAD = ROOT / "examples" / "access.bad.yml"
TODAY = date(2026, 10, 8)

BASE = {
    "version": 1,
    "teams": ["payments", "scoring"],
    "environments": ["dev", "prod"],
    "roles": {
        "viewer": {"vault": ["read", "list"], "kubernetes": "view", "gitlab": "reporter"},
        "developer": {"vault": ["read", "list"], "kubernetes": "edit", "gitlab": "developer"},
        "deployer": {"vault": ["read", "create", "update"], "gitlab": "maintainer"},
        "approver": {"gitlab": "maintainer"},
        "break-glass": {"vault": ["read", "delete"], "kubernetes": "admin", "gitlab": "maintainer"},
    },
    "people": {
        "alice": {"team": "payments", "status": "active"},
        "bob": {"team": "payments", "status": "active"},
        "zoe": {"team": "scoring", "status": "active"},
        "gone": {"team": "payments", "status": "offboarded"},
    },
    "groups": {"devs": ["alice", "bob"]},
    "grants": [],
}


@pytest.fixture
def doc():
    return copy.deepcopy(BASE)


@pytest.fixture
def make(doc):
    def _make(*grants, **overrides):
        d = copy.deepcopy(doc)
        d["grants"] = list(grants)
        d.update(overrides)
        return parse(d)

    return _make


def g(subject="alice", role="viewer", team="payments", env="dev", **kw):
    return {"subject": subject, "role": role, "team": team, "env": env, **kw}


@pytest.fixture
def good():
    return load(str(GOOD))


@pytest.fixture
def bad():
    return load(str(BAD))
