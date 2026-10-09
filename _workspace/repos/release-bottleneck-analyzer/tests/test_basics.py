from __future__ import annotations

import csv
import json

import pytest

from conftest import change, ts
from release_analyzer.model import DataError, load_changes, parse_ts
from release_analyzer.stats import mean, median, percentile
from release_analyzer.timeutil import Calendar, seconds_between

H = 3600


def test_percentile_matches_linear_interpolation():
    assert median([1, 2, 3, 4]) == 2.5
    assert percentile([1, 2, 3, 4], 90) == pytest.approx(3.7)
    assert percentile([5], 99) == 5 and percentile([1, 2], 0) == 1 and percentile([1, 2], 100) == 2


def test_stats_errors():
    for bad in (lambda: percentile([], 50), lambda: percentile([1], 101), lambda: mean([])):
        with pytest.raises(ValueError):
            bad()


def test_working_seconds_same_day_and_clipping():
    cal = Calendar()
    assert cal.working_seconds(ts(2, 10), ts(2, 12)) == 2 * H
    assert cal.working_seconds(ts(2, 7), ts(2, 20)) == 9 * H  # clipped to 09-18
    assert cal.working_seconds(ts(2, 19), ts(2, 20)) == 0


def test_working_seconds_skips_nights_and_weekends():
    cal = Calendar()
    assert cal.working_seconds(ts(2, 17), ts(3, 10)) == 2 * H  # Mon 17-18 + Tue 09-10
    assert cal.working_seconds(ts(6, 17), ts(9, 10)) == 2 * H  # Fri 17-18 + Mon 09-10, weekend skipped
    assert cal.working_seconds(ts(7, 9), ts(8, 18)) == 0  # Sat-Sun


def test_working_seconds_timezone_offset_and_reversed_range():
    assert Calendar(utc_offset_hours=3).working_seconds(ts(2, 5), ts(2, 8)) == 2 * H  # 08-11 local -> 09-11
    assert Calendar().working_seconds(ts(2, 12), ts(2, 10)) == 0


def test_seconds_between_wall_clock():
    assert seconds_between(ts(2, 9), ts(3, 9), None) == 24 * H
    assert seconds_between(ts(3, 9), ts(2, 9), None) == 0


def test_parse_ts_variants():
    assert parse_ts("2026-03-02T09:00:00Z") == ts(2, 9)
    assert parse_ts("2026-03-02T12:00:00+03:00") == ts(2, 9)
    assert parse_ts("2026-03-02T09:00:00") == ts(2, 9)  # naive -> UTC
    assert parse_ts("") is None and parse_ts(None) is None
    with pytest.raises(DataError):
        parse_ts("tomorrow")


def test_change_ordering_and_completeness():
    assert change().complete and change().in_order()
    assert not change(merged=ts(2, 10)).in_order()


def rows():
    return [
        {
            "id": "1",
            "created_at": "2026-03-02T09:00:00Z",
            "first_review_at": "2026-03-02T10:00:00Z",
            "approved_at": "2026-03-02T11:00:00Z",
            "merged_at": "2026-03-02T12:00:00Z",
            "deployed_at": "2026-03-02T13:00:00Z",
            "size": 5,
            "failed": "true",
        }
    ]


def test_load_json_and_csv(tmp_path):
    j = tmp_path / "a.json"
    j.write_text(json.dumps(rows()), encoding="utf-8")
    [c] = load_changes(j)
    assert c.failed and c.team == "unknown" and c.size == 5
    p = tmp_path / "a.csv"
    with p.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows()[0]))
        w.writeheader()
        w.writerows(rows())
    assert load_changes(p)[0].id == "1"


@pytest.mark.parametrize(
    "mutate",
    [lambda r: r.pop("id"), lambda r: r.update(created_at="nope"), lambda r: r.update(size="x")],
)
def test_bad_rows_raise_with_row_number(tmp_path, mutate):
    r = rows()
    mutate(r[0])
    p = tmp_path / "a.json"
    p.write_text(json.dumps(r), encoding="utf-8")
    with pytest.raises(DataError, match="row 0"):
        load_changes(p)


def test_empty_duplicate_and_unreadable(tmp_path):
    p = tmp_path / "a.json"
    p.write_text("[]", encoding="utf-8")
    with pytest.raises(DataError, match="non-empty"):
        load_changes(p)
    p.write_text(json.dumps(rows() * 2), encoding="utf-8")
    with pytest.raises(DataError, match="duplicate"):
        load_changes(p)
    with pytest.raises(DataError, match="cannot read"):
        load_changes(tmp_path / "missing.json")
