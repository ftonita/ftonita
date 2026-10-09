"""access-as-code: validate | lint | compile | diff | review | rules | demo-state."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import date, timedelta
from pathlib import Path

from . import __version__
from .compile import compile_access, effective, write
from .demo import make_drifted_state
from .drift import diff
from .lint import RULES, lint
from .model import AccessFileError, load


def _today(a: argparse.Namespace) -> date:
    return date.fromisoformat(a.today) if a.today else date.today()


def _cmd_validate(a: argparse.Namespace) -> int:
    acc = load(a.file)
    print(f"{a.file}: OK ({len(acc.people)} people, {len(acc.roles)} roles, {len(acc.grants)} grants)")
    return 0


def _cmd_lint(a: argparse.Namespace) -> int:
    violations = lint(load(a.file), _today(a))
    if a.format == "json":
        print(json.dumps([v.__dict__ for v in violations], indent=2))
    else:
        for v in violations:
            print(v)
        errs = sum(v.severity == "error" for v in violations)
        warns = sum(v.severity == "warning" for v in violations)
        print(f"{errs} error(s), {warns} warning(s), {len(violations) - errs - warns} info")
    failing = {"error", "warning"} if a.strict else {"error"}
    return 1 if any(v.severity in failing for v in violations) else 0


def _cmd_compile(a: argparse.Namespace) -> int:
    paths = write(compile_access(load(a.file), _today(a)), a.out)
    print(f"wrote {len(paths)} files to {a.out}")
    return 0


def _cmd_diff(a: argparse.Namespace) -> int:
    desired = compile_access(load(a.file), _today(a)).as_state()
    try:
        actual = json.loads(Path(a.actual).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AccessFileError([f"cannot read {a.actual}: {exc}"]) from exc
    drift = diff(desired, actual)
    for d in drift:
        print(d)
    print(f"{len(drift)} difference(s)" if drift else "no drift")
    return 1 if drift else 0


def _cmd_review(a: argparse.Namespace) -> int:
    acc, today = load(a.file), _today(a)
    horizon = today + timedelta(days=a.days)
    rows = [g for g in acc.grants if g.expires and today <= g.expires <= horizon]
    print(f"Grants expiring by {horizon}:")
    for g in sorted(rows, key=lambda g: g.expires):
        print(f"  {g.expires}  {g.describe()}  ticket={g.ticket or '-'}")
    prod_elevated = [
        g
        for g in acc.grants
        if g.env in acc.production and g.role in acc.roles and acc.roles[g.role].elevated
    ]
    print(f"Elevated production grants: {len(prod_elevated)}")
    for g in prod_elevated:
        print(f"  {g.describe()}  expires={g.expires or 'NEVER'}")
    print(f"People with effective access: {len({p for _, p in effective(acc, today)})}")
    return 0


def _cmd_rules(_: argparse.Namespace) -> int:
    for rid, text in RULES.items():
        print(f"{rid}  {text}")
    return 0


def _cmd_demo_state(a: argparse.Namespace) -> int:
    state = compile_access(load(a.file), _today(a)).as_state()
    Path(a.out).write_text(json.dumps(make_drifted_state(state), indent=2), encoding="utf-8")
    print(f"wrote synthetic drifted snapshot to {a.out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="access-as-code", description=__doc__)
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name: str, fn, help_: str, *, file: bool = True, today: bool = True) -> argparse.ArgumentParser:
        s = sub.add_parser(name, help=help_)
        if file:
            s.add_argument("file", help="access.yml")
        if today:
            s.add_argument("--today", help="YYYY-MM-DD (reproducible runs)")
        s.set_defaults(func=fn)
        return s

    add("validate", _cmd_validate, "schema and structure check", today=False)
    lp = add("lint", _cmd_lint, "least-privilege rules")
    lp.add_argument("--strict", action="store_true", help="warnings fail too")
    lp.add_argument("--format", choices=["text", "json"], default="text")
    add("compile", _cmd_compile, "emit Vault / Kubernetes / GitLab artifacts").add_argument(
        "--out", default="build"
    )
    add("diff", _cmd_diff, "desired vs actual snapshot").add_argument("--actual", required=True)
    add("review", _cmd_review, "expiring and elevated grants").add_argument("--days", type=int, default=30)
    add("rules", _cmd_rules, "list lint rules", file=False, today=False)
    add("demo-state", _cmd_demo_state, "write a synthetic drifted snapshot").add_argument(
        "--out", default="actual.json"
    )
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except AccessFileError as exc:
        for problem in exc.problems:
            print(f"error: {problem}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
