from __future__ import annotations

import json

import pytest

from vault_migration.models import LegacySecret, Secret
from vault_migration.sources import SourceError, load_legacy


def test_secret_never_leaks_through_repr_str_or_fstring():
    s = Secret("hunter2-hunter2")
    for rendered in (repr(s), str(s), f"{s}", f"{s!r}", "%s" % s):  # noqa: UP031
        assert "hunter2" not in rendered


def test_legacy_secret_repr_hides_value():
    rec = LegacySecret("1", "n", "a", "prod", "t", "password", Secret("topsecret-value"))
    assert "topsecret" not in repr(rec)


def test_secret_equality_and_reveal():
    assert Secret("a") == Secret("a") and Secret("a") != Secret("b")
    assert Secret("a").reveal() == "a"


def write(tmp_path, rows, name="x.json"):
    p = tmp_path / name
    p.write_text(json.dumps(rows), encoding="utf-8")
    return p


def row(**kw):
    return {"id": "1", "name": "n", "value": "v", **kw}


def test_load_json(tmp_path):
    [r] = load_legacy(
        write(tmp_path, [row(app="a", env="prod", last_rotated="2026-01-02", consumers="x; y")])
    )
    assert (r.app, r.env, r.last_rotated.isoformat(), r.consumers) == ("a", "prod", "2026-01-02", ("x", "y"))


def test_load_csv(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("id,name,value,app,env\n1,db,pw,orders,prod\n", encoding="utf-8")
    [r] = load_legacy(p)
    assert (r.name, r.app, r.value.reveal()) == ("db", "orders", "pw")


@pytest.mark.parametrize("missing", ["id", "name", "value"])
def test_missing_required_field(tmp_path, missing):
    bad = row()
    del bad[missing]
    with pytest.raises(SourceError, match=missing):
        load_legacy(write(tmp_path, [bad]))


def test_bad_date_duplicate_ids_and_shape(tmp_path):
    with pytest.raises(SourceError, match="invalid date"):
        load_legacy(write(tmp_path, [row(last_rotated="yesterday")]))
    with pytest.raises(SourceError, match="duplicate ids"):
        load_legacy(write(tmp_path, [row(), row()]))
    with pytest.raises(SourceError, match="list"):
        load_legacy(write(tmp_path, {"id": 1}))


def test_unreadable_and_broken_files(tmp_path):
    with pytest.raises(SourceError, match="cannot read"):
        load_legacy(tmp_path / "missing.json")
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(SourceError, match="cannot read"):
        load_legacy(bad)
