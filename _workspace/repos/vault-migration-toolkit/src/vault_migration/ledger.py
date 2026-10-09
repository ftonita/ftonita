"""Append-only JSONL ledger. Makes runs resumable and auditable. Contains no secret values."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class Entry:
    secret_id: str
    target: str
    status: str  # written | skipped_identical | conflict | failed | verified | mismatch | missing
    fingerprint8: str
    detail: str = ""
    at: str = ""


class Ledger:
    def __init__(self, directory: str | Path) -> None:
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.file = self.dir / "ledger.jsonl"

    def append(self, entry: Entry) -> None:
        stamped = Entry(
            **{**asdict(entry), "at": entry.at or datetime.now(timezone.utc).isoformat(timespec="seconds")}
        )
        with self.file.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(stamped)) + "\n")

    def entries(self) -> list[Entry]:
        if not self.file.exists():
            return []
        return [
            Entry(**json.loads(line)) for line in self.file.read_text(encoding="utf-8").splitlines() if line
        ]
