"""release-analyzer: demo | analyze | compare | simulate."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .analysis import analyze, compare, simulate, stage_durations
from .demo import write_demo
from .model import STAGES, DataError, load_changes
from .report import compare_markdown, stage_svg, to_json, to_markdown
from .timeutil import Calendar


def _calendar(a: argparse.Namespace) -> Calendar | None:
    return Calendar(utc_offset_hours=a.tz_offset) if a.working_hours else None


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--working-hours", action="store_true", help="count only Mon-Fri 09-18 (default: wall clock)")
    p.add_argument("--tz-offset", type=float, default=0.0, help="UTC offset for --working-hours")


def _emit(text: str, out: str | None) -> None:
    Path(out).write_text(text, encoding="utf-8") if out else sys.stdout.write(text)


def _cmd_demo(a: argparse.Namespace) -> int:
    for p in write_demo(a.out, a.seed):
        print(f"wrote {p} (synthetic)")
    return 0


def _cmd_analyze(a: argparse.Namespace) -> int:
    res = analyze(load_changes(a.input), _calendar(a))
    _emit(to_json(res) if a.format == "json" else to_markdown(res), a.out)
    if a.svg:
        Path(a.svg).write_text(stage_svg(res), encoding="utf-8")
    return 0


def _cmd_compare(a: argparse.Namespace) -> int:
    cal = _calendar(a)
    rows = compare(analyze(load_changes(a.before), cal), analyze(load_changes(a.after), cal))
    _emit(compare_markdown(rows, Path(a.before).stem, Path(a.after).stem), a.out)
    return 0


def _cmd_simulate(a: argparse.Namespace) -> int:
    if a.stage not in STAGES:
        raise DataError(f"stage must be one of {', '.join(STAGES)}")
    changes = [c for c in load_changes(a.input) if c.complete and c.in_order()]
    dur = [stage_durations(c, _calendar(a)) for c in changes]
    base = simulate(dur, a.stage, 0.0)
    new = simulate(dur, a.stage, a.reduction)
    print(
        f"mean lead time {base:.1f} h -> {new:.1f} h if '{a.stage}' is cut by {a.reduction:.0%} "
        f"({(new - base) / base:+.0%})"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="release-analyzer", description=__doc__)
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("demo", help="write synthetic before/after datasets")
    d.add_argument("--out", default="demo")
    d.add_argument("--seed", type=int, default=11)
    d.set_defaults(func=_cmd_demo)
    an = sub.add_parser("analyze", help="stage breakdown, DORA metrics, recommendations")
    an.add_argument("input")
    an.add_argument("--format", choices=["markdown", "json"], default="markdown")
    an.add_argument("--out")
    an.add_argument("--svg", help="also write a stage-share chart")
    _add_common(an)
    an.set_defaults(func=_cmd_analyze)
    c = sub.add_parser("compare", help="before/after comparison table")
    c.add_argument("before")
    c.add_argument("after")
    c.add_argument("--out")
    _add_common(c)
    c.set_defaults(func=_cmd_compare)
    s = sub.add_parser("simulate", help="what if one stage were shorter?")
    s.add_argument("input")
    s.add_argument("--stage", required=True)
    s.add_argument("--reduction", type=float, required=True, help="0..1, e.g. 0.5 for -50%%")
    _add_common(s)
    s.set_defaults(func=_cmd_simulate)
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (DataError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
