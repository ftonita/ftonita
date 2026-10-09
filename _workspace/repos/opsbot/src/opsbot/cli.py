"""opsbot: check-config | replay | run."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import __version__
from .alertmanager import AlertmanagerClient, AlertmanagerError
from .audit import AuditLog
from .backends import Alert, SyntheticBackend
from .config import ConfigError, load_config
from .core import OpsBot

DEMO_NOW = datetime(2026, 10, 9, 10, 0, tzinfo=timezone.utc)


class HybridBackend(SyntheticBackend):
    """Alerts and silences from a real Alertmanager; everything else stays synthetic."""

    def __init__(self, base: SyntheticBackend, am: AlertmanagerClient) -> None:
        self.__dict__.update(base.__dict__)
        self._am = am

    def alerts(self) -> list[Alert]:
        return self._am.alerts()

    def silence(self, alert_name: str, duration: timedelta, author: str, reason: str) -> str:
        return self._am.silence(alert_name, duration, author, reason)


def _cmd_check(a: argparse.Namespace) -> int:
    cfg = load_config(a.config)
    print(f"{a.config}: OK ({len(cfg.users)} users, {len(cfg.services)} services, prod={list(cfg.prod_environments)})")
    return 0


def _cmd_replay(a: argparse.Namespace) -> int:
    """Run a transcript against the synthetic backend: lines are '<user name or id>: <message>'."""
    cfg = load_config(a.config)
    clock = {"now": DEMO_NOW}
    codes = iter(a.codes.split(",")) if a.codes else None
    bot = OpsBot(
        cfg,
        SyntheticBackend.demo(DEMO_NOW),
        AuditLog(),
        lambda: clock["now"],
        (lambda n: next(codes)) if codes else None,
    )
    by_name = {u.name: u.id for u in cfg.users.values()}
    for raw in Path(a.transcript).read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.startswith("#"):
            continue
        if raw.startswith("+"):  # "+90s" advances the fake clock
            clock["now"] += timedelta(seconds=int(raw[1:].rstrip("s")))
            continue
        who, _, text = raw.partition(":")
        uid = by_name.get(who.strip()) or int(who.strip())
        print(f"> {who.strip()}: {text.strip()}")
        reply = bot.handle(uid, text.strip())
        print("\n".join(f"  {line}" for line in (reply or "(no reply)").splitlines()))
    return 0


def _cmd_run(a: argparse.Namespace) -> int:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("error: set TELEGRAM_BOT_TOKEN in the environment (never in the config file)", file=sys.stderr)
        return 2
    cfg = load_config(a.config)
    backend = SyntheticBackend.demo(datetime.now(timezone.utc))
    if a.alertmanager:
        backend = HybridBackend(backend, AlertmanagerClient(a.alertmanager))
    from .telegram_app import run_polling

    asyncio.run(run_polling(token, OpsBot(cfg, backend, AuditLog(a.audit_file))))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="opsbot", description=__doc__)
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check-config")
    c.add_argument("config")
    c.set_defaults(func=_cmd_check)
    r = sub.add_parser("replay", help="run a transcript against the synthetic backend (no Telegram needed)")
    r.add_argument("config")
    r.add_argument("transcript")
    r.add_argument("--codes", help="comma-separated confirmation codes for reproducible output")
    r.set_defaults(func=_cmd_replay)
    n = sub.add_parser("run", help="start the Telegram bot (long polling)")
    n.add_argument("config")
    n.add_argument("--audit-file", default="audit.jsonl")
    n.add_argument("--alertmanager", help="Alertmanager base URL for real alerts/silences")
    n.set_defaults(func=_cmd_run)
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (ConfigError, AlertmanagerError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
