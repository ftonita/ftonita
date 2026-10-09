"""Markdown, JSON and SVG renderers."""

from __future__ import annotations

import json
from dataclasses import asdict
from xml.sax.saxutils import escape

from .analysis import Analysis


def to_json(a: Analysis) -> str:
    return json.dumps(asdict(a), indent=2, default=str)


def to_markdown(a: Analysis, title: str = "Release bottleneck report") -> str:
    top = next(s for s in a.stages if s.name == a.bottleneck)
    d, b = a.dora, a.batches
    lines = [
        f"# {title}",
        "",
        f"**Median lead time {d.lead_p50_h:.1f} h** (p90 {d.lead_p90_h:.1f} h, {a.calendar}). "
        f"Biggest bottleneck: **{top.label}** = {top.share:.0%} of lead time.",
        "",
        f"Changes analysed: {a.analyzed} of {a.total}.",
        "",
    ]
    if a.issues:
        lines += ["## Data quality", "", *[f"- {i}" for i in a.issues], ""]
    lines += [
        "## Where the time goes",
        "",
        "| Stage | Mean h | p50 h | p90 h | Share |",
        "|---|--:|--:|--:|--:|",
    ]
    lines += [
        f"| {s.label}{' **<- bottleneck**' if s.name == a.bottleneck else ''} | {s.mean_h:.1f} | {s.p50_h:.1f} "
        f"| {s.p90_h:.1f} | {s.share:.0%} |"
        for s in a.stages
    ]
    mttr = f"{d.mttr_p50_h:.1f} h" if d.mttr_p50_h is not None else "n/a"
    lines += [
        "",
        "## DORA-style metrics",
        "",
        f"- Deployments: {d.deployments} ({d.deploys_per_week:.1f} per week)",
        f"- Change failure rate: {d.change_failure_rate:.0%}",
        f"- Time to restore (p50): {mttr}",
        "",
        "## Batching",
        "",
        f"- Median changes per deployment: {b.median_size:.0f} (max {b.max_size})",
        f"- Most common deploy day: {b.top_weekday} ({b.top_weekday_share:.0%} of deployments)",
    ]
    if a.ci_p50_min is not None:
        lines += [
            "",
            "## CI",
            "",
            f"- Pipeline duration p50 {a.ci_p50_min:.0f} min, p90 {a.ci_p90_min:.0f} min",
        ]
    lines += ["", "## Teams", "", "| Team | Changes | Lead p50 h | Slowest stage |", "|---|--:|--:|---|"]
    lines += [
        f"| {t} | {v['changes']} | {v['lead_p50_h']:.1f} | {v['top_stage']} ({v['top_stage_share']:.0%}) |"
        for t, v in a.teams.items()
    ]
    if a.recommendations:
        lines += ["", "## Recommendations", ""]
        for r in a.recommendations:
            est = (
                f" Cutting this stage by 50% would save about {r.saving_h:.1f} h of mean lead time."
                if r.saving_h
                else ""
            )
            lines += [f"**{r.id}. {r.title}.** {r.evidence}{est}", f"> {r.action}", ""]
    else:
        lines += ["", "## Recommendations", "", "No stage exceeds the built-in thresholds."]
    return "\n".join(lines).rstrip() + "\n"


def stage_svg(a: Analysis, title: str = "Share of lead time by stage") -> str:
    """A single stacked horizontal bar with a legend. Colours are distinguishable without hue (labels inside)."""
    colors = ["#3b6ea5", "#6a9fd1", "#d9a441", "#c0504d"]
    width, x0, bar_w, y = 760, 20, 720, 56
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} 190" role="img" '
        f'aria-label="{escape(title)}" font-family="sans-serif" font-size="13">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{x0}" y="26" font-size="15" font-weight="bold">{escape(title)} '
        f"(median lead time {a.dora.lead_p50_h:.1f} h)</text>",
    ]
    x = float(x0)
    for i, s in enumerate(a.stages):
        w = bar_w * s.share
        parts.append(f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="38" fill="{colors[i]}"/>')
        if w > 42:
            parts.append(
                f'<text x="{x + w / 2:.1f}" y="{y + 24}" fill="white" text-anchor="middle" '
                f'font-weight="bold">{s.share:.0%}</text>'
            )
        x += w
    for i, s in enumerate(a.stages):
        ly = 120 + (i // 2) * 24
        lx = x0 + (i % 2) * 370
        mark = " (bottleneck)" if s.name == a.bottleneck else ""
        parts.append(f'<rect x="{lx}" y="{ly - 11}" width="14" height="14" fill="{colors[i]}"/>')
        parts.append(f'<text x="{lx + 22}" y="{ly}">{escape(s.label)}: {s.mean_h:.1f} h mean{mark}</text>')
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def compare_markdown(rows: list[dict[str, float | str]], before_name: str, after_name: str) -> str:
    lines = [f"| Metric | {before_name} | {after_name} | Change |", "|---|--:|--:|--:|"]
    for r in rows:
        fmt = "{:.0%}" if "rate" in str(r["metric"]) else "{:.1f}"
        lines.append(
            f"| {r['metric']} | {fmt.format(r['before'])} | {fmt.format(r['after'])} | {r['change_pct']:+.0f}% |"
        )
    return "\n".join(lines) + "\n"
