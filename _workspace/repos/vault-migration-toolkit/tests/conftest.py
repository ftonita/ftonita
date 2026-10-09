from __future__ import annotations

import pytest

from stub_vault import StubState, make_server
from vault_migration.backends import MemoryVault, VaultHTTP
from vault_migration.demo import RULES_YAML, build_records
from vault_migration.fingerprint import load_or_create_key
from vault_migration.ledger import Ledger
from vault_migration.rules import Rules
from vault_migration.sources import load_legacy

KEY = b"k" * 32


@pytest.fixture
def key() -> bytes:
    return KEY


@pytest.fixture
def demo_files(tmp_path):
    import json

    legacy = tmp_path / "legacy.json"
    legacy.write_text(json.dumps(build_records()), encoding="utf-8")
    rules = tmp_path / "rules.yml"
    rules.write_text(RULES_YAML, encoding="utf-8")
    return legacy, rules


@pytest.fixture
def demo_secrets(demo_files):
    return load_legacy(demo_files[0])


@pytest.fixture
def rules(demo_files) -> Rules:
    return Rules.from_file(str(demo_files[1]))


@pytest.fixture
def ledger(tmp_path) -> Ledger:
    return Ledger(tmp_path / "state")


@pytest.fixture
def state_key(tmp_path) -> bytes:
    return load_or_create_key(tmp_path / "state")


@pytest.fixture
def memory_vault() -> MemoryVault:
    return MemoryVault()


@pytest.fixture
def stub():
    state = StubState()
    server, url = make_server(state)
    yield state, VaultHTTP(url, state.token, retries=3, timeout=3)
    server.shutdown()
