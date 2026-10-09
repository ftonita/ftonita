from __future__ import annotations

from datetime import date

import pytest

from vault_migration.analyze import analyze, is_weak
from vault_migration.models import LegacySecret, Secret
from vault_migration.report import inventory_report

TODAY = date(2026, 10, 8)
KEY = b"k" * 32


def sec(i, value="Str0ng-Value-123!", env="prod", team="t", rotated=date(2026, 9, 1), name="db"):
    return LegacySecret(i, name, "app", env, team, "password", Secret(value), rotated)


@pytest.mark.parametrize(
    ("v", "weak"),
    [("short", True), ("changeme", True), ("aaaaaaaaaaaaaaaa", True), ("Str0ng-Value-123!", False)],
)
def test_is_weak(v, weak):
    assert is_weak(v) is weak


def kinds(findings):
    return {(f.kind, f.severity) for f in findings}


def test_clean_secret_has_no_findings():
    assert analyze([sec("1")], KEY, TODAY) == []


def test_weak_prod_is_high_weak_dev_is_medium():
    assert ("weak", "high") in kinds(analyze([sec("1", "password1")], KEY, TODAY))
    assert ("weak", "medium") in kinds(analyze([sec("1", "password1", env="dev")], KEY, TODAY))


def test_same_value_across_environments_is_high_when_prod_involved():
    f = analyze([sec("1", env="stage"), sec("2", env="prod")], KEY, TODAY)
    assert ("shared_across_envs", "high") in kinds(f)
    f = analyze([sec("1", env="dev"), sec("2", env="stage")], KEY, TODAY)
    assert ("shared_across_envs", "medium") in kinds(f)


def test_same_value_same_env_is_low_duplicate():
    assert ("duplicate", "low") in kinds(analyze([sec("1"), sec("2", name="other")], KEY, TODAY))


def test_staleness_threshold_and_unknown_rotation():
    assert analyze([sec("1", rotated=date(2025, 10, 8))], KEY, TODAY) == []  # exactly 365 days
    assert ("stale", "medium") in kinds(analyze([sec("1", rotated=date(2025, 10, 7))], KEY, TODAY))
    assert ("stale", "medium") in kinds(analyze([sec("1", rotated=None)], KEY, TODAY))
    assert analyze([sec("1", rotated=date(2025, 6, 1))], KEY, TODAY, stale_days=600) == []


def test_unowned_secret_is_flagged():
    assert ("unowned", "low") in kinds(analyze([sec("1", team="")], KEY, TODAY))


def test_findings_are_sorted_high_first():
    f = analyze([sec("1", team=""), sec("2", "password1")], KEY, TODAY)
    assert [x.severity for x in f] == sorted((x.severity for x in f), key=["high", "medium", "low"].index)


def test_report_never_contains_secret_values(demo_secrets):
    text = inventory_report(demo_secrets, analyze(demo_secrets, KEY, TODAY))
    for s in demo_secrets:
        assert s.value.reveal() not in text
    assert "SYNTHETIC" not in text and "changeme" not in text


def test_demo_inventory_surfaces_every_planted_problem(demo_secrets):
    f = analyze(demo_secrets, KEY, TODAY)
    assert {"weak", "shared_across_envs", "stale", "unowned"} <= {x.kind for x in f}
