from __future__ import annotations

import pytest

from vault_migration.backends import CasMismatch, FileFakeVault, MemoryVault, VaultError, VaultHTTP


def test_http_refuses_plain_http_to_remote_hosts():
    with pytest.raises(VaultError, match="plain http"):
        VaultHTTP("http://vault.example.com", "t")


def test_from_env_requires_addr_and_token(monkeypatch):
    monkeypatch.delenv("VAULT_ADDR", raising=False)
    monkeypatch.delenv("VAULT_TOKEN", raising=False)
    with pytest.raises(VaultError, match="VAULT_ADDR"):
        VaultHTTP.from_env()
    monkeypatch.setenv("VAULT_ADDR", "https://vault.example.com")
    monkeypatch.setenv("VAULT_TOKEN", "t")
    assert VaultHTTP.from_env().addr == "https://vault.example.com"


def test_mount_lifecycle_over_http(stub):
    state, vault = stub
    assert vault.mount_exists("kv-a") is False
    vault.create_mount("kv-a")
    assert vault.mount_exists("kv-a") is True and "kv-a" in state.mounts


def test_write_read_roundtrip_with_metadata(stub):
    state, vault = stub
    vault.create_mount("kv-a")
    assert vault.read("kv-a", "dev/app/x") is None
    assert vault.write("kv-a", "dev/app/x", {"value": "v1"}, 0, {"legacy_id": "S1"}) == 1
    got = vault.read("kv-a", "dev/app/x")
    assert (got.data, got.version, got.custom_metadata) == ({"value": "v1"}, 1, {"legacy_id": "S1"})


def test_cas_conflict_is_detected(stub):
    _, vault = stub
    vault.create_mount("kv-a")
    vault.write("kv-a", "p", {"value": "1"}, 0, {})
    with pytest.raises(CasMismatch):
        vault.write("kv-a", "p", {"value": "2"}, 0, {})
    assert vault.write("kv-a", "p", {"value": "2"}, 1, {}) == 2


def test_wrong_token_is_an_error_not_silent(stub):
    _, vault = stub
    vault.token = "wrong"
    with pytest.raises(VaultError, match="HTTP 403"):
        vault.mount_exists("kv-a")


def test_transient_5xx_is_retried(stub):
    state, vault = stub
    state.mounts.add("kv-a")
    state.fail_next_with = [503, 502]
    assert vault.read("kv-a", "nothing") is None
    assert len(state.requests) == 3


def test_persistent_5xx_gives_up(stub):
    state, vault = stub
    state.fail_next_with = [500, 500, 500, 500]
    with pytest.raises(VaultError, match="HTTP 500"):
        vault.mount_exists("kv-a")


def test_unreachable_server():
    v = VaultHTTP("http://127.0.0.1:9", "t", retries=2, timeout=0.5)
    with pytest.raises(VaultError, match="cannot reach"):
        v.mount_exists("kv-a")


def test_memory_vault_requires_mount_and_cas():
    v = MemoryVault()
    with pytest.raises(VaultError, match="no secret engine"):
        v.write("kv-a", "p", {}, 0, {})
    v.create_mount("kv-a")
    v.write("kv-a", "p", {"value": "1"}, 0, {})
    with pytest.raises(CasMismatch):
        v.write("kv-a", "p", {"value": "2"}, 0, {})


def test_file_fake_vault_persists(tmp_path):
    f = tmp_path / "fake.json"
    a = FileFakeVault(f)
    a.create_mount("kv-a")
    a.write("kv-a", "p", {"value": "1"}, 0, {"k": "v"})
    b = FileFakeVault(f)
    assert b.read("kv-a", "p").data == {"value": "1"} and b.mount_exists("kv-a")


def test_full_migration_through_real_http(stub, demo_secrets, rules, ledger, state_key):
    from vault_migration.migrate import apply, verify
    from vault_migration.rules import plan

    _, vault = stub
    items, _ = plan(demo_secrets, rules)
    by_id = {s.id: s for s in demo_secrets}
    res = apply(items, by_id, vault, ledger, state_key, execute=True, create_mounts=True)
    assert len(res.written) == 36 and res.ok
    assert verify(items, by_id, vault, ledger, state_key).ok
    assert len(apply(items, by_id, vault, ledger, state_key, execute=True).skipped) == 36
