"""Deterministic drift for demos and tests: what an audit of a hand-edited system looks like."""

from __future__ import annotations

import copy
from typing import Any


def make_drifted_state(state: dict[str, Any]) -> dict[str, Any]:
    s = copy.deepcopy(state)
    groups = s["vault_groups"]
    first_group = sorted(groups)[0]
    groups[first_group] = groups[first_group][1:]  # a member was removed by hand
    prod_group = next(k for k in sorted(groups) if "-prod-" in k)
    groups[prod_group] = [*groups[prod_group], "zed"]  # someone was added out of band
    pol = next(k for k in sorted(s["vault_policies"]) if "-dev-developer" in k)
    s["vault_policies"][pol] = s["vault_policies"][pol].replace('"read"', '"read", "delete"')  # widened
    s["vault_policies"]["legacy-admin"] = 'path "*" {\n  capabilities = ["sudo"]\n}\n'  # undeclared
    del s["kubernetes"][sorted(s["kubernetes"])[0]]  # binding missing
    team, member = next(
        (t, m)
        for t in sorted(s["gitlab"])
        for m, lvl in sorted(s["gitlab"][t].items())
        if lvl != "maintainer"
    )
    s["gitlab"][team][member] = "maintainer"  # silently escalated
    return s
