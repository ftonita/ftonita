"""Append-only audit trail (JSONL). Arguments are truncated and stripped of control characters."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

_CTRL = re.compile(r"[\x00-\x1f\x7f]")


def clean(text: str, limit: int = 200) -> str:
    return _CTRL.sub(" ", text)[:limit]


@dataclass(frozen=True)
class Entry:
    at: str
    user_id: int
    user: str
    command: str
    args: str
    outcome: str  # ok | denied | invalid | error | rate_limited | pending
    detail: str = ""


class AuditLog:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else None
        self.entries: list[Entry] = []

    def record(
        self, now: datetime, user_id: int, user: str, command: str, args: str, outcome: str, detail: str = ""
    ) -> Entry:
        e = Entry(
            now.isoformat(timespec="seconds"),
            user_id,
            clean(user, 64),
            clean(command, 32),
            clean(args),
            outcome,
            clean(detail),
        )
        self.entries.append(e)
        if self.path:
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(asdict(e)) + "\n")
        return e

    def tail(self, n: int) -> list[Entry]:
        return self.entries[-n:]
