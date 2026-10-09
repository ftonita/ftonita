"""Load a legacy export. Supported: JSON (list of objects) and CSV with the same columns."""

from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path
from typing import Any

from .models import LegacySecret, Secret

REQUIRED = ("id", "name", "value")


class SourceError(ValueError):
    pass


def _parse_date(raw: Any) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(str(raw))
    except ValueError as exc:
        raise SourceError(f"invalid date {raw!r}: expected YYYY-MM-DD") from exc


def _record(row: dict[str, Any], index: int) -> LegacySecret:
    for key in REQUIRED:
        if not row.get(key):
            raise SourceError(f"record {index}: missing required field '{key}'")
    consumers = row.get("consumers") or ()
    if isinstance(consumers, str):
        consumers = tuple(c.strip() for c in consumers.split(";") if c.strip())
    return LegacySecret(
        id=str(row["id"]),
        name=str(row["name"]),
        app=str(row.get("app") or ""),
        env=str(row.get("env") or ""),
        team=str(row.get("team") or ""),
        kind=str(row.get("kind") or "password"),
        value=Secret(str(row["value"])),
        last_rotated=_parse_date(row.get("last_rotated")),
        consumers=tuple(consumers),
    )


def load_legacy(path: str | Path) -> list[LegacySecret]:
    p = Path(path)
    try:
        if p.suffix.lower() == ".csv":
            with p.open(newline="", encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
        else:
            rows = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SourceError(f"cannot read {p}: {exc}") from exc
    if not isinstance(rows, list):
        raise SourceError("export must be a list of records")
    records = [_record(r, i) for i, r in enumerate(rows)]
    ids = [r.id for r in records]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise SourceError(f"duplicate ids in export: {', '.join(dupes)}")
    return records
