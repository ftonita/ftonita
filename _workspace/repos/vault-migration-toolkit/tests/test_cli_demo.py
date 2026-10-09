from __future__ import annotations

import json

import pytest

from vault_migration.cli import main
from vault_migration.demo import build_records, write_demo


@pytest.fixture
def env(tmp_path):
    legacy, rules = write_demo(tmp_path / "data")
    state = tmp_path / "state"
    common = [
        "--source",
        str(legacy),
        "--rules",
        str(rules),
        "--state",
        str(state),
        "--backend",
        f"fake:{tmp_path / 'fake.json'}",
    ]
    return tmp_path, legacy, rules, state, common


def test_demo_is_deterministic_and_synthetic():
    a, b = build_records(7), build_records(7)
    assert a == b and build_records(8) != a
    assert all(r["value"].startswith("SYNTHETIC-") or r["value"] in {"changeme", "Ab1!"} for r in a)


def test_inventory_prints_report_and_fail_on_high(env, capsys):
    _, legacy, _, state, _ = env
    args = ["inventory", "--source", str(legacy), "--state", str(state), "--today", "2026-10-08"]
    assert main(args) == 0
    out = capsys.readouterr().out
    assert "shared_across_envs" in out and "SYNTHETIC" not in out
    assert main([*args, "--fail-on"]) == 1


def test_inventory_to_file(env):
    tmp, legacy, _, state, _ = env
    out = tmp / "inv.md"
    assert main(["inventory", "--source", str(legacy), "--state", str(state), "--out", str(out)]) == 0
    assert out.read_text(encoding="utf-8").startswith("# Secret inventory")


def test_plan_report(env, capsys):
    _, legacy, rules, _, _ = env
    assert main(["plan", "--source", str(legacy), "--rules", str(rules)]) == 0
    out = capsys.readouterr().out
    assert "Manual queue: **2**" in out and "kv-payments/prod/orders/db_password" in out


def test_end_to_end_dry_run_execute_idempotent_verify_tamper(env, capsys):
    tmp, _, _, _, common = env
    assert main(["apply", *common]) == 0
    assert "DRY RUN" in capsys.readouterr().out and not (tmp / "fake.json").exists()
    assert main(["apply", *common, "--execute", "--create-mounts"]) == 0
    assert "written=36" in capsys.readouterr().out
    assert main(["apply", *common, "--execute"]) == 0
    assert "skipped=36" in capsys.readouterr().out
    assert main(["verify", *common]) == 0
    fake = json.loads((tmp / "fake.json").read_text(encoding="utf-8"))
    fake["store"]["kv-scoring::dev/scorer/api_key"]["data"]["value"] = "tampered"
    (tmp / "fake.json").write_text(json.dumps(fake), encoding="utf-8")
    assert main(["verify", *common]) == 1
    assert "mismatch: S014" in capsys.readouterr().out
    assert main(["apply", *common, "--execute"]) == 1  # conflict, never silently overwritten
    assert main(["apply", *common, "--execute", "--overwrite"]) == 0
    assert main(["verify", *common]) == 0


def test_ledger_has_no_secret_values_after_cli_run(env):
    tmp, legacy, _, state, common = env
    main(["apply", *common, "--execute", "--create-mounts"])
    assert "SYNTHETIC" not in (state / "ledger.jsonl").read_text(encoding="utf-8")


def test_errors_exit_2(env, capsys, tmp_path):
    assert main(["inventory", "--source", str(tmp_path / "nope.json")]) == 2
    assert main(["apply", "--source", "x", "--rules", "y", "--backend", "bogus"]) == 2
    assert "error:" in capsys.readouterr().err


def test_demo_command(tmp_path, capsys):
    assert main(["demo", "--out", str(tmp_path / "d")]) == 0
    assert (tmp_path / "d" / "legacy.json").exists() and "synthetic" in capsys.readouterr().out
