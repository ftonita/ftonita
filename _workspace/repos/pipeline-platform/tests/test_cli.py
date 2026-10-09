from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from pipeline_platform.cli import main

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "consumer-app" / "argocd.platform.yml"


def test_validate_ok(capsys):
    assert main(["validate", "--config", str(EXAMPLE)]) == 0
    assert "OK" in capsys.readouterr().out


def test_validate_reports_every_problem(tmp_path, capsys):
    bad = tmp_path / "bad.yml"
    bad.write_text("version: 2\napp: {name: Bad_Name}\n", encoding="utf-8")
    assert main(["validate", "--config", str(bad)]) == 2
    err = capsys.readouterr().err
    assert "app.name" in err and "problem(s)" in err


def test_validate_missing_file(tmp_path, capsys):
    assert main(["validate", "--config", str(tmp_path / "nope.yml")]) == 2
    assert "cannot read" in capsys.readouterr().err


def test_validate_broken_yaml(tmp_path, capsys):
    bad = tmp_path / "bad.yml"
    bad.write_text("a: [unclosed\n", encoding="utf-8")
    assert main(["validate", "--config", str(bad)]) == 2


def test_generate_writes_file_for_current_context(tmp_path, monkeypatch, capsys):
    for k in ("CI_COMMIT_TAG", "CI_MERGE_REQUEST_IID", "CI_PIPELINE_SOURCE"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("CI_COMMIT_BRANCH", "main")
    monkeypatch.setenv("CI_DEFAULT_BRANCH", "main")
    out = tmp_path / "child.yml"
    assert main(["generate", "--config", str(EXAMPLE), "--out", str(out)]) == 0
    doc = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert "deploy:dev" in doc and "context: branch" in capsys.readouterr().out


def test_generate_refuses_invalid_config(tmp_path):
    bad = tmp_path / "bad.yml"
    bad.write_text("version: 1\n", encoding="utf-8")
    out = tmp_path / "child.yml"
    assert main(["generate", "--config", str(bad), "--out", str(out)]) == 2
    assert not out.exists()


def test_generate_to_stdout(monkeypatch, capsys):
    monkeypatch.setenv("CI_COMMIT_TAG", "v1.0.0")
    assert main(["generate", "--config", str(EXAMPLE), "--out", "-"]) == 0
    assert "deploy:prod" in capsys.readouterr().out


def test_bump_tag(tmp_path, capsys):
    src = Path(__file__).resolve().parent.parent / "examples/gitops-repo/apps/orders-api/dev/values.yaml"
    dst = tmp_path / "values.yaml"
    shutil.copy(src, dst)
    assert main(["bump-tag", "--file", str(dst), "--tag", "abc12345"]) == 0
    assert yaml.safe_load(dst.read_text(encoding="utf-8"))["image"]["tag"] == "abc12345"


def test_bump_tag_errors(tmp_path, capsys):
    f = tmp_path / "v.yaml"
    f.write_text("replicaCount: 1\n", encoding="utf-8")
    assert main(["bump-tag", "--file", str(f), "--tag", "abc"]) == 2
    assert main(["bump-tag", "--file", str(tmp_path / "missing.yaml"), "--tag", "abc"]) == 2
    assert main(["bump-tag", "--file", str(f), "--tag", "bad tag"]) == 2


def test_schema_command_prints_valid_json(capsys):
    import json

    assert main(["schema"]) == 0
    assert json.loads(capsys.readouterr().out)["title"].startswith("pipeline-platform")
