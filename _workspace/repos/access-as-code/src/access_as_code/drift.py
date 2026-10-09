"""Compare desired state (compiled) with an exported snapshot of what is actually configured."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

AREAS = ("vault_policies", "vault_groups", "kubernetes", "gitlab")


@dataclass(frozen=True)
class Drift:
    kind: str  # missing | extra | changed
    area: str
    key: str
    detail: str

    def __str__(self) -> str:
        return f"{self.kind:<8} {self.area}:{self.key}  {self.detail}"


def _norm(v: Any) -> Any:
    return v.strip() if isinstance(v, str) else v


def diff(desired: dict[str, Any], actual: dict[str, Any]) -> list[Drift]:
    out: list[Drift] = []
    for area in AREAS:
        want, have = desired.get(area, {}), actual.get(area, {})
        for key in sorted(set(want) | set(have)):
            if key not in have:
                out.append(Drift("missing", area, key, "declared but not configured"))
            elif key not in want:
                out.append(Drift("extra", area, key, "configured but not declared"))
            elif _norm(want[key]) != _norm(have[key]):
                out.append(Drift("changed", area, key, _describe(want[key], have[key])))
    return out


def _describe(want: Any, have: Any) -> str:
    if isinstance(want, list) and isinstance(have, list):
        extra, missing = sorted(set(have) - set(want)), sorted(set(want) - set(have))
        return "; ".join(
            p
            for p in (
                f"extra members {extra}" if extra else "",
                f"missing members {missing}" if missing else "",
            )
            if p
        )
    if isinstance(want, dict) and isinstance(have, dict):
        parts = []
        for k in sorted(set(want) | set(have)):
            if want.get(k) != have.get(k):
                parts.append(f"{k}: declared {want.get(k)!r}, actual {have.get(k)!r}")
        return "; ".join(parts)
    return "content differs"
