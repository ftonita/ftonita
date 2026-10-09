from __future__ import annotations

import copy
from datetime import timedelta

import pytest

from conftest import NOW, RAW
from opsbot.audit import AuditLog, clean
from opsbot.config import ConfigError, load_config, parse_config
from opsbot.confirm import ALPHABET, Confirmations
from opsbot.ratelimit import RateLimiter


def test_config_roles_and_hierarchy(cfg):
    assert cfg.users[2].at_least("operator") and not cfg.users[3].at_least("operator")
    assert cfg.users[4].at_least("approver") and cfg.prod_environments == ("prod",)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda r: r.update(users=[]),
        lambda r: r["users"].append({"id": 1, "name": "dup", "role": "viewer"}),
        lambda r: r["users"].append({"id": "x", "name": "bad", "role": "viewer"}),
        lambda r: r["users"].append({"id": 9, "name": "bad", "role": "root"}),
        lambda r: r.update(services=[]),
        lambda r: r.update(prod_environments=["nope"]),
        lambda r: r.update(surprise=1),
        lambda r: r.update(rate_limit={"burst": 0}),
    ],
)
def test_invalid_configs(mutate):
    raw = copy.deepcopy(RAW)
    mutate(raw)
    with pytest.raises(ConfigError):
        parse_config(raw)


def test_config_must_be_mapping_and_file_errors(tmp_path):
    with pytest.raises(ConfigError):
        parse_config(["x"])
    with pytest.raises(ConfigError, match="cannot read"):
        load_config(str(tmp_path / "missing.yml"))


def test_rate_limiter_burst_refill_and_isolation():
    rl = RateLimiter(burst=3, per_minute=60)  # 1 token / second
    assert [rl.allow(1, NOW) for _ in range(4)] == [True, True, True, False]
    assert rl.allow(2, NOW)  # other users unaffected
    assert not rl.allow(1, NOW + timedelta(milliseconds=500))
    assert rl.allow(1, NOW + timedelta(seconds=2))
    assert [rl.allow(1, NOW + timedelta(hours=1)) for _ in range(4)] == [True, True, True, False]  # capped at burst


def test_confirmations_single_use_expiry_and_case():
    c = Confirmations(60, lambda n: "ABC234")
    p = c.create(1, "x", lambda: "ran", NOW, needs_other=False)
    assert c.peek("abc234", NOW) is p and len(c) == 1
    assert c.take("abc234", NOW) is p and c.take("ABC234", NOW) is None
    c.create(1, "y", lambda: "", NOW, needs_other=False)
    assert c.take("ABC234", NOW + timedelta(seconds=60)) is None  # expired exactly at ttl


def test_confirmation_codes_are_unique_and_unambiguous():
    seq = iter(["AAAAAA", "AAAAAA", "BBBBBB"])
    c = Confirmations(60, lambda n: next(seq))
    a = c.create(1, "a", lambda: "", NOW, False)
    b = c.create(1, "b", lambda: "", NOW, False)
    assert a.code != b.code
    real = Confirmations(60)
    code = real.create(1, "z", lambda: "", NOW, False).code
    assert len(code) == 6 and set(code) <= set(ALPHABET) and not set("01OIl") & set(ALPHABET)


def test_audit_cleans_control_characters_and_truncates(tmp_path):
    assert clean("a\nb\x00c" + "x" * 500, 10) == "a b c" + "xxxxx"
    log = AuditLog(tmp_path / "a.jsonl")
    log.record(NOW, 1, "al\nice", "silence", "x" * 1000, "ok")
    line = (tmp_path / "a.jsonl").read_text(encoding="utf-8")
    assert line.count("\n") == 1 and len(log.entries[0].args) == 200 and "\\n" not in log.entries[0].user
