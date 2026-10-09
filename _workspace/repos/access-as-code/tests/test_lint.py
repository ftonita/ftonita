from __future__ import annotations

from datetime import date

import pytest

from access_as_code.lint import RULES, lint
from conftest import TODAY, g


def rules_of(acc, today=TODAY):
    return [v.rule for v in lint(acc, today)]


def test_good_file_has_no_errors_and_only_expected_notices(good):
    vs = lint(good, TODAY)
    assert [v.rule for v in vs if v.severity == "error"] == []
    assert {v.rule for v in vs} == {"AAC010", "AAC011"}


def test_bad_file_triggers_every_rule_id(bad):
    assert set(rules_of(bad)) == set(RULES)


def test_bad_file_exact_error_counts(bad):
    vs = lint(bad, TODAY)
    assert sum(v.severity == "error" for v in vs) == 11
    assert sum(v.severity == "warning" for v in vs) == 5


def test_sudo_is_forbidden(doc):
    from access_as_code.model import parse

    doc["roles"]["x"] = {"vault": ["sudo"]}
    assert "AAC001" in rules_of(parse(doc))


@pytest.mark.parametrize(
    ("grant", "fragment"),
    [
        (g(team="nope"), "unknown team"),
        (g(env="nope"), "unknown environment"),
        (g(role="nope"), "unknown role"),
        (g(subject="nobody"), "unknown subject"),
        (g(subject="group:nope"), "unknown subject"),
    ],
)
def test_unknown_references(make, grant, fragment):
    assert any(v.rule == "AAC002" and fragment in v.message for v in lint(make(grant), TODAY))


def test_invalid_grants_do_not_cascade_into_other_rules(make):
    vs = lint(make(g(env="nope", subject="gone")), TODAY)
    assert {v.rule for v in vs if v.severity == "error"} == {"AAC002"}


def test_prod_grant_needs_ticket(make):
    assert "AAC003" in rules_of(make(g(subject="group:devs", env="prod")))
    assert "AAC003" not in rules_of(make(g(subject="group:devs", env="prod", ticket="SEC-1")))


def test_direct_prod_grant_needs_expiry_within_90_days(make):
    no_expiry = g(env="prod", ticket="SEC-1")
    assert "AAC003" in rules_of(make(no_expiry))
    ok = g(env="prod", ticket="SEC-1", expires="2027-01-06")  # exactly 90 days
    assert "AAC003" not in rules_of(make(ok))
    late = g(env="prod", ticket="SEC-1", expires="2027-01-07")
    assert "AAC003" in rules_of(make(late))


def test_non_prod_needs_no_ticket_or_expiry(make):
    assert set(rules_of(make(g(subject="group:devs", env="dev")))) <= {"AAC010"}  # only "unused" notices


def test_elevated_role_in_prod_is_short_lived_and_ticketed(make):
    ok = g(role="break-glass", env="prod", ticket="SEC-9", expires="2026-10-15")
    assert "AAC004" not in rules_of(make(ok))
    for bad in (
        g(role="break-glass", env="prod", ticket="SEC-9", expires="2026-10-16"),
        g(role="break-glass", env="prod", expires="2026-10-10"),
    ):
        assert "AAC004" in rules_of(make(bad))
    assert "AAC004" not in rules_of(make(g(role="break-glass", env="dev")))


def test_offboarded_person_directly_or_via_group(make, doc):
    assert "AAC005" in rules_of(make(g(subject="gone")))
    assert "AAC005" in rules_of(make(g(subject="group:old"), groups={"old": ["gone"]}))


def test_expired_and_expiring_soon(make):
    assert "AAC006" in rules_of(make(g(expires="2026-10-07")))
    assert "AAC006" not in rules_of(make(g(expires="2026-10-08")))  # expires today: still valid
    assert "AAC011" in rules_of(make(g(expires="2026-10-22")))
    assert "AAC011" not in rules_of(make(g(expires="2026-10-23")))


def test_separation_of_duties_only_on_prod_and_same_team(make):
    base = {"ticket": "SEC-1", "expires": "2026-11-01", "env": "prod"}
    both = make(g(role="deployer", **base), g(role="approver", **base))
    assert "AAC007" in rules_of(both)
    other_person = make(g(role="deployer", **base), g(subject="bob", role="approver", **base))
    assert "AAC007" not in rules_of(other_person)
    dev = make(g(role="deployer", env="dev"), g(role="approver", env="dev"))
    assert "AAC007" not in rules_of(dev)


def test_separation_of_duties_through_a_group(make):
    base = {"ticket": "SEC-1", "env": "prod"}
    acc = make(
        g(subject="group:devs", role="deployer", **base),
        g(subject="alice", role="approver", expires="2026-11-01", **base),
    )
    assert any("alice" in v.message for v in lint(acc, TODAY) if v.rule == "AAC007")


def test_cross_team_requires_ticket(make):
    assert "AAC008" in rules_of(make(g(subject="zoe")))
    assert "AAC008" not in rules_of(make(g(subject="zoe", ticket="SEC-5")))


def test_duplicates_and_unused(make):
    vs = lint(make(g(), g()), TODAY)
    assert "AAC009" in {v.rule for v in vs}
    unused = {v.message for v in vs if v.rule == "AAC010"}
    assert "role 'developer' is never granted" in unused and "group 'devs' is never granted" in unused


def test_output_is_sorted_errors_first(bad):
    sev = [v.severity for v in lint(bad, TODAY)]
    assert sev == sorted(sev, key=["error", "warning", "info"].index)


def test_lint_is_pure_wrt_today(bad):
    assert [str(v) for v in lint(bad, TODAY)] == [str(v) for v in lint(bad, date(2026, 10, 8))]
