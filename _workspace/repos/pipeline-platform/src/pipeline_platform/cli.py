"""pipeline-platform command line: validate, generate, bump-tag, schema."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path

import yaml

from . import __version__
from .context import Context
from .generator import dump, generate
from .gitops import TagNotFoundError, bump_image_tag
from .schema import load_config, load_schema, validate


def _load_valid(path: str):
    try:
        doc = load_config(path)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"error: cannot read {path}: {exc}", file=sys.stderr)
        return None
    issues = validate(doc)
    if issues:
        print(f"{path} is invalid ({len(issues)} problem(s)):", file=sys.stderr)
        for issue in issues:
            print(f"  - {issue}", file=sys.stderr)
        return None
    return doc


def _cmd_validate(args: argparse.Namespace) -> int:
    doc = _load_valid(args.config)
    if doc is None:
        return 2
    print(f"{args.config}: OK")
    return 0


def _cmd_generate(args: argparse.Namespace) -> int:
    doc = _load_valid(args.config)
    if doc is None:
        return 2
    ctx = Context.from_env(os.environ)
    text = dump(generate(doc, ctx))
    if args.out == "-":
        sys.stdout.write(text)
    else:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out} (context: {ctx.kind})")
    return 0


def _cmd_bump(args: argparse.Namespace) -> int:
    path = Path(args.file)
    try:
        path.write_text(bump_image_tag(path.read_text(encoding="utf-8"), args.tag), encoding="utf-8")
    except (OSError, TagNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"{args.file}: image.tag -> {args.tag}")
    return 0


def _cmd_schema(_: argparse.Namespace) -> int:
    json.dump(load_schema(), sys.stdout, indent=2)
    print()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="pipeline-platform")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate", help="validate .platform.yml")
    v.add_argument("--config", default=".platform.yml")
    v.set_defaults(func=_cmd_validate)
    g = sub.add_parser("generate", help="emit the child pipeline for the current CI context")
    g.add_argument("--config", default=".platform.yml")
    g.add_argument("--out", default="child-pipeline.yml", help="output file or - for stdout")
    g.set_defaults(func=_cmd_generate)
    b = sub.add_parser("bump-tag", help="set image.tag in a Helm values file")
    b.add_argument("--file", required=True)
    b.add_argument("--tag", required=True)
    b.set_defaults(func=_cmd_bump)
    s = sub.add_parser("schema", help="print the JSON Schema")
    s.set_defaults(func=_cmd_schema)
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
