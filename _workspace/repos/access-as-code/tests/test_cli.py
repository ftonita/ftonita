from __future__ import annotations

import json

from access_as_code.cli import main
from conftest import BAD, GOOD

T = ["--today", "2026-10-08"]


def test_validate(capsys):
    assert main(["validate", str(GOOD)]) == 0
    assert "OK" in capsys.readouterr().out


def test_lint_exit_codes(capsys):
    assert main(["lint", str(GOOD), *T]) == 0
    assert main(["lint", str(GOOD), *T, "--strict"]) == 1  # AAC011 warning
    assert main(["lint", str(BAD), *T]) == 1
    assert "11 error(s)" in capsys.readouterr().out


def test_lint_json(capsys):
    main(["lint", str(BAD), *T, "--format", "json"])
    data = json.loads(capsys.readouterr().out)
    assert {"rule", "severity", "message"} <= set(data[0])


def test_compile_then_diff_is_clean_and_demo_state_drifts(tmp_path, capsys):
    out = tmp_path / "build"
    assert main(["compile", str(GOOD), *T, "--out", str(out)]) == 0
    assert (out / "vault" / "groups.json").exists()
    snap = tmp_path / "actual.json"
    assert main(["demo-state", str(GOOD), *T, "--out", str(snap)]) == 0
    capsys.readouterr()
    assert main(["diff", str(GOOD), *T, "--actual", str(snap)]) == 1
    text = capsys.readouterr().out
    assert "legacy-admin" in text and "6 difference(s)" in text


def test_diff_no_drift(tmp_path, capsys):
    from datetime import date

    from access_as_code.compile import compile_access
    from access_as_code.model import load

    snap = tmp_path / "s.json"
    snap.write_text(
        json.dumps(compile_access(load(str(GOOD)), date(2026, 10, 8)).as_state()), encoding="utf-8"
    )
    assert main(["diff", str(GOOD), *T, "--actual", str(snap)]) == 0
    assert "no drift" in capsys.readouterr().out


def test_review_lists_expiring_and_elevated(capsys):
    assert main(["review", str(GOOD), *T, "--days", "10"]) == 0
    out = capsys.readouterr().out
    assert "bob -> break-glass" in out and "Elevated production grants: 1" in out


def test_rules_listing(capsys):
    assert main(["rules"]) == 0
    assert "AAC007" in capsys.readouterr().out


def test_input_errors_exit_2(tmp_path, capsys):
    assert main(["validate", str(tmp_path / "missing.yml")]) == 2
    bad = tmp_path / "bad.yml"
    bad.write_text("version: 1\n", encoding="utf-8")
    assert main(["lint", str(bad)]) == 2
    broken = tmp_path / "broken.yml"
    broken.write_text("a: [", encoding="utf-8")
    assert main(["validate", str(broken)]) == 2
    assert main(["diff", str(GOOD), "--actual", str(tmp_path / "nope.json")]) == 2
    err = capsys.readouterr().err
    assert "error:" in err and "required property" in err


def test_schema_rejects_unknown_fields_and_bad_values(doc):
    import pytest

    from access_as_code.model import AccessFileError, parse

    doc["roles"]["viewer"]["vault"] = ["root"]
    doc["grants"] = [
        {"subject": "alice", "role": "viewer", "team": "payments", "env": "dev", "ticket": "bad"}
    ]
    doc["extra"] = 1
    with pytest.raises(AccessFileError) as e:
        parse(doc)
    assert len(e.value.problems) == 3
