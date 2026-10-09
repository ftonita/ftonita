from __future__ import annotations

import pytest

from vault_migration.backends import MemoryVault, VaultError
from vault_migration.migrate import apply, verify
from vault_migration.models import PlanItem, Target
from vault_migration.rules import plan


@pytest.fixture
def prepared(demo_secrets, rules):
    items, _ = plan(demo_secrets, rules)
    return items, {s.id: s for s in demo_secrets}


def run(prepared, vault, ledger, key, **kw):
    items, by_id = prepared
    return apply(items, by_id, vault, ledger, key, **{"execute": True, "create_mounts": True, **kw})


def test_dry_run_changes_nothing_and_writes_no_ledger(prepared, memory_vault, ledger, state_key):
    res = run(prepared, memory_vault, ledger, state_key, execute=False)
    assert len(res.would_write) == 36 and not res.written
    assert memory_vault.store == {} and memory_vault.mounts == set() and ledger.entries() == []


def test_execute_writes_values_and_metadata(prepared, memory_vault, ledger, state_key, demo_secrets):
    res = run(prepared, memory_vault, ledger, state_key)
    assert len(res.written) == 36 and res.ok
    stored = memory_vault.read("kv-payments", "dev/orders/db_password")
    src = next(s for s in demo_secrets if s.id == "S001")
    assert stored.data == {"value": src.value.reveal()}
    assert stored.custom_metadata["legacy_id"] == "S001" and stored.version == 1


def test_second_run_is_a_no_op(prepared, memory_vault, ledger, state_key):
    run(prepared, memory_vault, ledger, state_key)
    again = run(prepared, memory_vault, ledger, state_key)
    assert len(again.skipped) == 36 and not again.written
    assert all(s.version == 1 for s in memory_vault.store.values())


def test_existing_different_value_is_a_conflict_not_overwritten(prepared, memory_vault, ledger, state_key):
    run(prepared, memory_vault, ledger, state_key)
    memory_vault.store[("kv-payments", "dev/orders/db_password")] = memory_vault.store[
        ("kv-payments", "dev/orders/db_password")
    ].__class__({"value": "edited-in-vault"}, 1, {})
    res = run(prepared, memory_vault, ledger, state_key)
    assert res.conflicts == ["S001"] and not res.ok
    assert memory_vault.read("kv-payments", "dev/orders/db_password").data["value"] == "edited-in-vault"


def test_overwrite_uses_cas_and_bumps_version(prepared, memory_vault, ledger, state_key, demo_secrets):
    run(prepared, memory_vault, ledger, state_key)
    memory_vault.store[("kv-payments", "dev/orders/db_password")] = memory_vault.store[
        ("kv-payments", "dev/orders/db_password")
    ].__class__({"value": "edited"}, 1, {})
    res = run(prepared, memory_vault, ledger, state_key, overwrite=True)
    assert res.written == ["S001"]
    assert memory_vault.read("kv-payments", "dev/orders/db_password").version == 2


def test_missing_mount_fails_cleanly_without_create_mounts(prepared, memory_vault, ledger, state_key):
    res = run(prepared, memory_vault, ledger, state_key, create_mounts=False)
    assert len(res.failed) == 36 and not res.written
    assert "create-mounts" in ledger.entries()[0].detail


def test_partial_failure_is_resumable(prepared, ledger, state_key):
    class Flaky(MemoryVault):
        broken = True

        def write(self, mount, path, data, cas, metadata):  # noqa: ANN001
            if self.broken and path.endswith("prod/orders/db_password"):
                raise VaultError("HTTP 503")
            return super().write(mount, path, data, cas, metadata)

    v = Flaky()
    first = run(prepared, v, ledger, state_key)
    assert first.failed == ["S005"] and len(first.written) == 35
    v.broken = False
    second = run(prepared, v, ledger, state_key)
    assert second.written == ["S005"] and len(second.skipped) == 35 and second.ok


def test_ledger_and_results_contain_no_secret_values(prepared, memory_vault, ledger, state_key, demo_secrets):
    run(prepared, memory_vault, ledger, state_key)
    text = ledger.file.read_text(encoding="utf-8")
    assert all(s.value.reveal() not in text for s in demo_secrets)
    assert all(len(e.fingerprint8) == 8 for e in ledger.entries())


def test_verify_detects_match_mismatch_and_missing(prepared, memory_vault, ledger, state_key):
    items, by_id = prepared
    run(prepared, memory_vault, ledger, state_key)
    ok = verify(items, by_id, memory_vault, ledger, state_key)
    assert ok.ok and len(ok.verified) == 36
    k = ("kv-scoring", "prod/scorer/api_key")
    memory_vault.store[k] = memory_vault.store[k].__class__({"value": "x"}, 1, {})
    del memory_vault.store[("kv-scoring", "dev/scorer/api_key")]
    bad = verify(items, by_id, memory_vault, ledger, state_key)
    assert bad.mismatched == ["S018"] and bad.missing == ["S014"] and not bad.ok


def test_verify_against_empty_vault_reports_everything_missing(prepared, memory_vault, ledger, state_key):
    items, by_id = prepared
    assert len(verify(items, by_id, memory_vault, ledger, state_key).missing) == 36


def test_cas_mismatch_is_reported_as_failure(prepared, ledger, state_key):
    from vault_migration.backends import CasMismatch

    class Racy(MemoryVault):
        def write(self, *a, **k):  # noqa: ANN002, ANN003
            raise CasMismatch("lost the race")

    items, by_id = prepared
    res = apply(items[:1], by_id, Racy(), ledger, state_key, execute=True, create_mounts=True)
    assert res.failed == ["S001"]


def test_single_item_target_str():
    assert str(PlanItem("1", Target("kv-a", "dev/x/y")).target) == "kv-a/dev/x/y"
