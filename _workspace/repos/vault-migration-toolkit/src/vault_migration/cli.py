"""vault-migrate: demo | inventory | plan | apply | verify."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from . import __version__
from .analyze import analyze
from .backends import Backend, FileFakeVault, VaultError, VaultHTTP
from .demo import write_demo
from .fingerprint import load_or_create_key
from .ledger import Ledger
from .migrate import apply, verify
from .report import inventory_report, plan_report
from .rules import Rules, plan
from .sources import SourceError, load_legacy


def _backend(spec: str) -> Backend:
    if spec == "http":
        return VaultHTTP.from_env()
    if spec.startswith("fake:"):
        return FileFakeVault(spec[5:])
    raise VaultError("backend must be 'http' or 'fake:<file>'")


def _common(p: argparse.ArgumentParser, *, rules: bool = False, state: bool = True) -> None:
    p.add_argument("--source", required=True, help="legacy export (.json or .csv)")
    if rules:
        p.add_argument("--rules", required=True, help="mapping rules YAML")
    if state:
        p.add_argument("--state", default="migration-state", help="ledger and fingerprint key directory")


def _cmd_demo(a: argparse.Namespace) -> int:
    legacy, rules = write_demo(a.out, a.seed)
    print(f"wrote {legacy} and {rules} (synthetic data only)")
    return 0


def _cmd_inventory(a: argparse.Namespace) -> int:
    secrets = load_legacy(a.source)
    key = load_or_create_key(a.state)
    findings = analyze(secrets, key, date.fromisoformat(a.today) if a.today else date.today(), a.stale_days)
    text = inventory_report(secrets, findings)
    Path(a.out).write_text(text, encoding="utf-8") if a.out else sys.stdout.write(text)
    return 1 if a.fail_on and any(f.severity == "high" for f in findings) else 0


def _cmd_plan(a: argparse.Namespace) -> int:
    items, unmapped = plan(load_legacy(a.source), Rules.from_file(a.rules))
    text = plan_report(items, unmapped)
    Path(a.out).write_text(text, encoding="utf-8") if a.out else sys.stdout.write(text)
    return 0


def _prepare(a: argparse.Namespace):
    secrets = load_legacy(a.source)
    items, unmapped = plan(secrets, Rules.from_file(a.rules))
    return {s.id: s for s in secrets}, items, unmapped, load_or_create_key(a.state), Ledger(a.state)


def _cmd_apply(a: argparse.Namespace) -> int:
    by_id, items, unmapped, key, ledger = _prepare(a)
    res = apply(
        items,
        by_id,
        _backend(a.backend),
        ledger,
        key,
        execute=a.execute,
        overwrite=a.overwrite,
        create_mounts=a.create_mounts,
    )
    mode = "EXECUTED" if a.execute else "DRY RUN (nothing written; add --execute)"
    print(
        f"{mode}: written={len(res.written)} would_write={len(res.would_write)} "
        f"skipped={len(res.skipped)} conflicts={len(res.conflicts)} failed={len(res.failed)} "
        f"manual_queue={len(unmapped)}"
    )
    for sid in res.conflicts:
        print(f"  conflict: {sid} (target exists with a different value; use --overwrite to replace)")
    for sid in res.failed:
        print(f"  failed: {sid} (see ledger)")
    return 0 if res.ok else 1


def _cmd_verify(a: argparse.Namespace) -> int:
    by_id, items, unmapped, key, ledger = _prepare(a)
    v = verify(items, by_id, _backend(a.backend), ledger, key)
    print(
        f"verified={len(v.verified)} mismatched={len(v.mismatched)} missing={len(v.missing)} "
        f"manual_queue={len(unmapped)}"
    )
    for sid in v.mismatched:
        print(f"  mismatch: {sid}")
    for sid in v.missing:
        print(f"  missing: {sid}")
    return 0 if v.ok else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="vault-migrate", description=__doc__)
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("demo", help="write a synthetic legacy export and rules")
    d.add_argument("--out", default="demo")
    d.add_argument("--seed", type=int, default=7)
    d.set_defaults(func=_cmd_demo)
    i = sub.add_parser("inventory", help="analyse the legacy export (no Vault access)")
    _common(i)
    i.add_argument("--out")
    i.add_argument("--today", help="YYYY-MM-DD, for reproducible staleness")
    i.add_argument("--stale-days", type=int, default=365)
    i.add_argument("--fail-on", action="store_true", help="exit 1 if any high-severity finding")
    i.set_defaults(func=_cmd_inventory)
    pl = sub.add_parser("plan", help="map secrets to Vault mounts and paths")
    _common(pl, rules=True, state=False)
    pl.add_argument("--out")
    pl.set_defaults(func=_cmd_plan)
    for name, fn in (("apply", _cmd_apply), ("verify", _cmd_verify)):
        s = sub.add_parser(name)
        _common(s, rules=True)
        s.add_argument("--backend", default="http", help="'http' (VAULT_ADDR/VAULT_TOKEN) or 'fake:<file>'")
        if name == "apply":
            s.add_argument("--execute", action="store_true", help="really write (default is a dry run)")
            s.add_argument("--overwrite", action="store_true")
            s.add_argument("--create-mounts", action="store_true")
        s.set_defaults(func=fn)
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (SourceError, VaultError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
