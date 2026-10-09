"""Markdown reports. Values never appear; only ids, names, paths and 8-char fingerprints."""

from __future__ import annotations

from collections import Counter

from .analyze import Finding
from .models import LegacySecret, PlanItem, Unmapped


def inventory_report(secrets: list[LegacySecret], findings: list[Finding]) -> str:
    by_sev = Counter(f.severity for f in findings)
    lines = [
        "# Secret inventory",
        "",
        f"- Secrets: **{len(secrets)}**",
        f"- Findings: **{len(findings)}** "
        f"(high {by_sev['high']}, medium {by_sev['medium']}, low {by_sev['low']})",
        "",
        "| Severity | Kind | Secrets | Detail |",
        "|---|---|---|---|",
    ]
    lines += [f"| {f.severity} | {f.kind} | {', '.join(f.secret_ids)} | {f.detail} |" for f in findings]
    return "\n".join(lines) + "\n"


def plan_report(items: list[PlanItem], unmapped: list[Unmapped]) -> str:
    lines = [
        "# Migration plan",
        "",
        f"- Mapped: **{len(items)}**",
        f"- Manual queue: **{len(unmapped)}**",
        "",
        "| Secret | Target |",
        "|---|---|",
    ]
    lines += [f"| {i.secret_id} | `{i.target}` |" for i in items]
    if unmapped:
        lines += ["", "## Manual queue", "", "| Secret | Reason |", "|---|---|"]
        lines += [f"| {u.secret_id} | {u.reason} |" for u in unmapped]
    return "\n".join(lines) + "\n"
