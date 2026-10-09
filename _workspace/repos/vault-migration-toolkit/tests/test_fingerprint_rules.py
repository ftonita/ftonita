from __future__ import annotations

import stat

import pytest

from vault_migration.fingerprint import fingerprint, load_or_create_key
from vault_migration.models import LegacySecret, Secret
from vault_migration.rules import Rules, plan, slug


def sec(i="1", name="db", app="orders", env="prod", team="payments", value="v"):
    return LegacySecret(i, name, app, env, team, "password", Secret(value))


def test_fingerprint_is_keyed_and_deterministic():
    assert fingerprint(b"a" * 32, "x") == fingerprint(b"a" * 32, Secret("x"))
    assert fingerprint(b"a" * 32, "x") != fingerprint(b"b" * 32, "x")
    assert "x" not in fingerprint(b"a" * 32, "x")


def test_key_is_created_once_with_private_permissions(tmp_path):
    k1 = load_or_create_key(tmp_path / "st")
    assert load_or_create_key(tmp_path / "st") == k1 and len(k1) == 32
    assert stat.S_IMODE((tmp_path / "st" / "fingerprint.key").stat().st_mode) == 0o600


@pytest.mark.parametrize(
    ("raw", "expected"), [("Payments Team", "payments-team"), (" A/B ", "a-b"), ("--x--", "x")]
)
def test_slug(raw, expected):
    assert slug(raw) == expected


def test_plan_maps_with_aliases_and_owner_fallback():
    r = Rules.from_dict(
        {
            "team_aliases": {"Pay": "payments"},
            "env_aliases": {"production": "prod"},
            "app_owners": {"reports": "platform"},
        }
    )
    items, unmapped = plan([sec("1", team="Pay", env="production"), sec("2", team="", app="reports")], r)
    assert [str(i.target) for i in items] == ["kv-payments/prod/orders/db", "kv-platform/prod/reports/db"]
    assert unmapped == []


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [({"team": ""}, "no owning team"), ({"env": "uat"}, "environment"), ({"app": ""}, "missing app")],
)
def test_ambiguous_records_go_to_manual_queue(kwargs, reason):
    items, unmapped = plan([sec(**kwargs)], Rules())
    assert items == [] and reason in unmapped[0].reason


def test_colliding_targets_are_not_silently_merged():
    items, unmapped = plan([sec("1"), sec("2")], Rules())
    assert len(items) == 1 and "already taken by 1" in unmapped[0].reason


def test_plan_is_deterministic_regardless_of_input_order():
    a, b = sec("1", name="x"), sec("2", name="y")
    assert plan([a, b], Rules())[0] == plan([b, a], Rules())[0]


def test_unknown_rule_keys_rejected():
    with pytest.raises(ValueError, match="unknown rule keys"):
        Rules.from_dict({"mount_prefx": "kv-"})


def test_demo_rules_plan(demo_secrets, rules):
    items, unmapped = plan(demo_secrets, rules)
    assert (len(items), len(unmapped)) == (36, 2)
    assert {u.secret_id for u in unmapped} == {"S037", "S038"}
