from __future__ import annotations

import pytest

from conftest import change, ts
from release_analyzer.analysis import analyze, compare, recommend, simulate, stage_durations
from release_analyzer.timeutil import Calendar

H = 3600


def test_stage_durations_of_a_known_change():
    d = stage_durations(change(), None)  # Mon 09,11,15,16 -> Tue 16
    assert d == {"review_wait": 2 * H, "review": 4 * H, "merge_wait": 1 * H, "release_wait": 24 * H}


def test_analysis_on_two_known_changes():
    a = change("A")  # lead 31 h
    b = change("B", created=ts(2, 10), first=ts(2, 12), approved=ts(2, 14), merged=ts(2, 15), deployed=ts(2, 17))
    res = analyze([a, b])  # B: 2,2,1,2 = 7 h
    assert res.analyzed == 2 and res.in_flight == 0
    assert res.dora.lead_p50_h == pytest.approx((31 + 7) / 2)
    st = {s.name: s for s in res.stages}
    assert st["release_wait"].mean_h == pytest.approx(13.0) and st["review_wait"].mean_h == pytest.approx(2.0)
    assert sum(s.share for s in res.stages) == pytest.approx(1.0)
    assert res.bottleneck == "release_wait"


def test_dora_deployments_batches_failures_and_mttr():
    cs = [
        change(f"C{i}", release_id="R1", deployed=ts(3, 16), failed=(i == 0), restored=ts(3, 20) if i == 0 else None)
        for i in range(4)
    ]
    cs.append(change("C9", release_id="R2", deployed=ts(5, 16)))
    res = analyze(cs)
    assert res.dora.deployments == 2 and res.batches.max_size == 4 and res.batches.median_size == 2.5
    assert res.dora.change_failure_rate == pytest.approx(1 / 5)
    assert res.dora.mttr_p50_h == pytest.approx(4.0)
    assert res.batches.top_weekday in {"Tuesday", "Thursday"}


def test_mttr_is_none_without_restore_times():
    assert analyze([change(failed=True)]).dora.mttr_p50_h is None


def test_without_release_ids_deploys_group_by_hour():
    cs = [change("A", deployed=ts(3, 16, 5)), change("B", deployed=ts(3, 16, 40)), change("C", deployed=ts(3, 18))]
    assert analyze(cs).dora.deployments == 2


def test_incomplete_and_out_of_order_changes_are_excluded_and_reported():
    good = change("OK")
    in_flight = change("FLY")
    in_flight = type(in_flight)(**{**in_flight.__dict__, "deployed_at": None})
    backwards = change("BAD", merged=ts(2, 10))
    res = analyze([good, in_flight, backwards])
    assert (res.total, res.analyzed, res.in_flight) == (3, 1, 1)
    assert any("out of order" in i and "BAD" in i for i in res.issues)
    assert any("not yet in production" in i for i in res.issues)


def test_nothing_analyzable_raises():
    with pytest.raises(ValueError, match="no complete"):
        analyze([change(merged=ts(2, 10))])


def test_working_hours_mode_ignores_the_weekend():
    fri = dict(created=ts(6, 16), first=ts(6, 17), approved=ts(9, 10), merged=ts(9, 11), deployed=ts(9, 12))
    wall = analyze([change(**fri)])
    work = analyze([change(**fri)], Calendar())
    assert wall.stages[1].mean_h == pytest.approx(65.0)  # Fri 17:00 -> Mon 10:00 wall clock
    assert work.stages[1].mean_h == pytest.approx(2.0)  # Fri 17-18 + Mon 09-10
    assert work.calendar.startswith("working hours")


def test_simulate_math_and_validation():
    dur = [stage_durations(change(), None)]
    assert simulate(dur, "release_wait", 0) == pytest.approx(31.0)
    assert simulate(dur, "release_wait", 0.5) == pytest.approx(19.0)
    assert simulate(dur, "release_wait", 1) == pytest.approx(7.0)
    for stage, red in (("nope", 0.5), ("review", 1.5), ("review", -0.1)):
        with pytest.raises(ValueError):
            simulate(dur, stage, red)


def test_team_breakdown_and_size_split():
    small = change("S", team="a", size=5)
    big = change("L", team="b", size=500, deployed=ts(9, 16))
    res = analyze([small, big])
    assert set(res.teams) == {"a", "b"} and res.teams["a"]["top_stage"] == "release_wait"
    assert res.size_split["large_p50_h"] > res.size_split["small_p50_h"]


def ids(res):
    return {r.id for r in res.recommendations}


def test_recommendations_fire_on_the_dominant_stage(before):
    res = analyze(before)
    assert res.bottleneck == "release_wait" and "R2" in ids(res)
    r2 = next(r for r in res.recommendations if r.id == "R2")
    assert r2.saving_h and r2.saving_h > 0 and "batched" in r2.evidence and "Thursday" in r2.evidence


def test_healthy_flow_has_no_release_queue_recommendation(after):
    res = analyze(after)
    assert "R2" not in ids(res) and res.dora.deploys_per_week > 5


def test_review_wait_recommendation():
    slow = [change(f"C{i}", first=ts(4, 9), deployed=ts(4, 17), approved=ts(4, 10), merged=ts(4, 11)) for i in range(3)]
    assert "R1" in ids(analyze(slow))


def test_failure_and_recovery_recommendations():
    cs = [change(f"C{i}", failed=(i < 2), restored=ts(5, 16) if i < 2 else None) for i in range(5)]
    res = analyze(cs)
    assert {"R6", "R7"} <= ids(res)


def test_ci_speed_changes_the_merge_wait_advice():
    slow = [
        change(f"C{i}", approved=ts(2, 15), merged=ts(3, 15), deployed=ts(3, 16), pipeline=40 * 60) for i in range(3)
    ]
    r3 = next(r for r in analyze(slow).recommendations if r.id == "R3")
    assert "Parallelize" in r3.action
    fast = [change(f"C{i}", approved=ts(2, 15), merged=ts(3, 15), deployed=ts(3, 16), pipeline=300) for i in range(3)]
    assert "auto-merge" in next(r for r in analyze(fast).recommendations if r.id == "R3").action


def test_recommend_is_pure_given_analysis(before):
    res = analyze(before)
    dur = [stage_durations(c, None) for c in before if c.complete and c.in_order()]
    assert [r.id for r in recommend(res, dur)] == [r.id for r in res.recommendations]


def test_compare_rows(before, after):
    rows = {r["metric"]: r for r in compare(analyze(before), analyze(after))}
    assert rows["Lead time p50 (h)"]["change_pct"] < -80
    assert rows["Deployments per week"]["after"] > rows["Deployments per week"]["before"]


def test_demo_is_deterministic(before_rows):
    from release_analyzer.demo import build

    assert build("before") == before_rows and build("before", seed=12) != before_rows
    assert sum(1 for r in before_rows if not r["deployed_at"]) == 3
