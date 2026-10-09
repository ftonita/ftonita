"""Stage breakdown, DORA metrics, batching, segments, what-if simulation and recommendations."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import timedelta

from .model import STAGE_LABELS, STAGES, Change
from .stats import mean, median, percentile
from .timeutil import Calendar, seconds_between

HOUR = 3600.0
THRESHOLDS = {
    "share": 0.30,
    "merge_share": 0.25,
    "ci_p90_min": 20.0,
    "batch": 4,
    "weekday": 0.5,
    "size_ratio": 2.0,
    "cfr": 0.15,
    "mttr_h": 24.0,
}
WHAT_IF = 0.5


@dataclass(frozen=True)
class StageStats:
    name: str
    label: str
    mean_h: float
    p50_h: float
    p90_h: float
    share: float


@dataclass(frozen=True)
class Dora:
    deployments: int
    deploys_per_week: float
    lead_mean_h: float
    lead_p50_h: float
    lead_p90_h: float
    change_failure_rate: float
    mttr_p50_h: float | None


@dataclass(frozen=True)
class Batches:
    deployments: int
    median_size: float
    max_size: int
    top_weekday: str
    top_weekday_share: float


@dataclass(frozen=True)
class Recommendation:
    id: str
    title: str
    evidence: str
    action: str
    stage: str | None = None
    saving_h: float | None = None  # mean lead-time saving if the stage were cut by WHAT_IF


@dataclass
class Analysis:
    total: int
    analyzed: int
    in_flight: int
    issues: list[str]
    calendar: str
    stages: list[StageStats]
    bottleneck: str
    dora: Dora
    batches: Batches
    teams: dict[str, dict[str, float | str]]
    size_split: dict[str, float]
    ci_p50_min: float | None
    ci_p90_min: float | None
    recommendations: list[Recommendation] = field(default_factory=list)


def stage_durations(c: Change, cal: Calendar | None) -> dict[str, float]:
    pts = [c.created_at, c.first_review_at, c.approved_at, c.merged_at, c.deployed_at]
    return {s: seconds_between(a, b, cal) for s, a, b in zip(STAGES, pts[:-1], pts[1:], strict=True)}


def _lead(d: dict[str, float]) -> float:
    return sum(d.values())


def simulate(durations: list[dict[str, float]], stage: str, reduction: float) -> float:
    """Mean lead time (hours) if `stage` were shortened by `reduction` (0..1) for every change."""
    if stage not in STAGES or not 0 <= reduction <= 1:
        raise ValueError("unknown stage or reduction outside 0..1")
    return mean([_lead(d) - reduction * d[stage] for d in durations]) / HOUR


def _unique_deployments(changes: list[Change]) -> dict[str, list[Change]]:
    groups: dict[str, list[Change]] = defaultdict(list)
    for c in changes:
        key = c.release_id or c.deployed_at.replace(minute=0, second=0, microsecond=0).isoformat()
        groups[key].append(c)
    return groups


def _batches(groups: dict[str, list[Change]]) -> Batches:
    sizes = [len(v) for v in groups.values()]
    days = Counter(v[0].deployed_at.strftime("%A") for v in groups.values())
    top, n = days.most_common(1)[0]
    return Batches(len(groups), median(sizes), max(sizes), top, n / len(groups))


def analyze(changes: list[Change], cal: Calendar | None = None) -> Analysis:
    issues: list[str] = []
    in_flight = [c for c in changes if not c.complete]
    ordered = [c for c in changes if c.complete and c.in_order()]
    bad = [c for c in changes if c.complete and not c.in_order()]
    if bad:
        issues.append(
            f"{len(bad)} change(s) excluded: timestamps out of order ({', '.join(c.id for c in bad[:5])}"
            f"{', ...' if len(bad) > 5 else ''})"
        )
    if in_flight:
        issues.append(
            f"{len(in_flight)} change(s) not yet in production or missing timestamps (excluded from lead time)"
        )
    if not ordered:
        raise ValueError("no complete, correctly ordered changes to analyze")

    dur = [stage_durations(c, cal) for c in ordered]
    leads = [_lead(d) for d in dur]
    total_mean = mean(leads)
    stages = [
        StageStats(
            s,
            STAGE_LABELS[s],
            mean([d[s] for d in dur]) / HOUR,
            median([d[s] for d in dur]) / HOUR,
            percentile([d[s] for d in dur], 90) / HOUR,
            mean([d[s] for d in dur]) / total_mean if total_mean else 0.0,
        )
        for s in STAGES
    ]
    bottleneck = max(stages, key=lambda s: s.share).name

    groups = _unique_deployments(ordered)
    first, last = min(c.created_at for c in ordered), max(c.deployed_at for c in ordered)
    weeks = max((last - first) / timedelta(days=7), 1 / 7)
    failed = [c for c in ordered if c.failed]
    restores = [
        (c.restored_at - c.deployed_at).total_seconds() / HOUR
        for c in failed
        if c.restored_at and c.restored_at >= c.deployed_at
    ]
    dora = Dora(
        len(groups),
        len(groups) / weeks,
        total_mean / HOUR,
        median(leads) / HOUR,
        percentile(leads, 90) / HOUR,
        len(failed) / len(ordered),
        median(restores) if restores else None,
    )

    teams: dict[str, dict[str, float | str]] = {}
    for team in sorted({c.team for c in ordered}):
        idx = [i for i, c in enumerate(ordered) if c.team == team]
        t_mean = mean([leads[i] for i in idx])
        top = max(STAGES, key=lambda s: mean([dur[i][s] for i in idx]))
        teams[team] = {
            "changes": len(idx),
            "lead_p50_h": median([leads[i] for i in idx]) / HOUR,
            "top_stage": top,
            "top_stage_share": mean([dur[i][top] for i in idx]) / t_mean,
        }

    cut = median([c.size for c in ordered])
    small = [leads[i] for i, c in enumerate(ordered) if c.size <= cut]
    large = [leads[i] for i, c in enumerate(ordered) if c.size > cut]
    size_split = {
        "size_cutoff": cut,
        "small_p50_h": median(small) / HOUR if small else 0.0,
        "large_p50_h": median(large) / HOUR if large else 0.0,
    }

    ci = [c.pipeline_seconds / 60 for c in ordered if c.pipeline_seconds is not None]
    result = Analysis(
        len(changes),
        len(ordered),
        len(in_flight),
        issues,
        "working hours (Mon-Fri)" if cal else "wall clock",
        stages,
        bottleneck,
        dora,
        _batches(groups),
        teams,
        size_split,
        median(ci) if ci else None,
        percentile(ci, 90) if ci else None,
    )
    result.recommendations = recommend(result, dur)
    return result


def recommend(a: Analysis, dur: list[dict[str, float]]) -> list[Recommendation]:
    t, out = THRESHOLDS, []
    by = {s.name: s for s in a.stages}

    def saving(stage: str) -> float:
        return mean([_lead(d) for d in dur]) / HOUR - simulate(dur, stage, WHAT_IF)

    s = by["review_wait"]
    if s.share >= t["share"]:
        out.append(
            Recommendation(
                "R1",
                "Cut time-to-first-review",
                f"{s.share:.0%} of lead time is waiting for a first review (p90 {s.p90_h:.1f} h).",
                "Review SLA, auto-assign via CODEOWNERS rotation, chat notifications for stale MRs.",
                "review_wait",
                saving("review_wait"),
            )
        )
    s = by["release_wait"]
    if s.share >= t["share"]:
        why = []
        if a.batches.median_size >= t["batch"]:
            why.append(f"releases are batched (median {a.batches.median_size:.0f} changes per deployment)")
        if a.batches.top_weekday_share >= t["weekday"]:
            why.append(f"{a.batches.top_weekday_share:.0%} of deployments happen on {a.batches.top_weekday}")
        out.append(
            Recommendation(
                "R2",
                "Shorten the release queue",
                f"{s.share:.0%} of lead time is spent between merge and production"
                f"{' (' + '; '.join(why) + ')' if why else ''}.",
                "Deploy every merge to a pre-production stage automatically, promote with one click, "
                "decouple deploy from release with feature flags.",
                "release_wait",
                saving("release_wait"),
            )
        )
    s = by["merge_wait"]
    if s.share >= t["merge_share"]:
        slow_ci = a.ci_p90_min is not None and a.ci_p90_min > t["ci_p90_min"]
        out.append(
            Recommendation(
                "R3",
                "Speed up approval-to-merge",
                f"{s.share:.0%} of lead time passes between approval and merge"
                + (f"; CI p90 is {a.ci_p90_min:.0f} min." if slow_ci else "."),
                "Parallelize and cache CI jobs."
                if slow_ci
                else "Enable auto-merge on approval or a merge queue; CI is not the main delay.",
                "merge_wait",
                saving("merge_wait"),
            )
        )
    s = by["review"]
    if s.share >= t["share"]:
        out.append(
            Recommendation(
                "R4",
                "Reduce review back-and-forth",
                f"{s.share:.0%} of lead time is between first review and approval.",
                "Smaller MRs, pre-review checklists and linters, pair on large changes.",
                "review",
                saving("review"),
            )
        )
    sp = a.size_split
    if sp["small_p50_h"] and sp["large_p50_h"] / sp["small_p50_h"] >= t["size_ratio"]:
        out.append(
            Recommendation(
                "R5",
                "Keep changes small",
                f"Changes above {sp['size_cutoff']:.0f} lines take {sp['large_p50_h']:.1f} h (p50) vs "
                f"{sp['small_p50_h']:.1f} h for smaller ones.",
                "Set a soft size limit and split work behind feature flags.",
            )
        )
    if a.dora.change_failure_rate >= t["cfr"]:
        out.append(
            Recommendation(
                "R6",
                "Lower the change failure rate",
                f"{a.dora.change_failure_rate:.0%} of changes fail in production.",
                "Progressive delivery (canary), automated smoke tests after deploy, automatic rollback.",
            )
        )
    if a.dora.mttr_p50_h is not None and a.dora.mttr_p50_h >= t["mttr_h"]:
        out.append(
            Recommendation(
                "R7",
                "Shorten recovery time",
                f"Median time to restore is {a.dora.mttr_p50_h:.1f} h.",
                "One-command rollback, runbooks, alert routing to the owning team.",
            )
        )
    return out


def compare(before: Analysis, after: Analysis) -> list[dict[str, float | str]]:
    def row(name: str, b: float, a: float) -> dict[str, float | str]:
        return {"metric": name, "before": b, "after": a, "change_pct": (a - b) / b * 100 if b else 0.0}

    rows = [
        row("Lead time p50 (h)", before.dora.lead_p50_h, after.dora.lead_p50_h),
        row("Lead time p90 (h)", before.dora.lead_p90_h, after.dora.lead_p90_h),
        row("Deployments per week", before.dora.deploys_per_week, after.dora.deploys_per_week),
        row("Change failure rate", before.dora.change_failure_rate, after.dora.change_failure_rate),
    ]
    b = {s.name: s for s in before.stages}
    rows += [row(f"{s.label} (mean h)", b[s.name].mean_h, s.mean_h) for s in after.stages]
    return rows
