"""Change records and robust parsing. Bad rows are reported, not silently dropped."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STAGES = ("review_wait", "review", "merge_wait", "release_wait")
STAGE_LABELS = {
    "review_wait": "Waiting for first review",
    "review": "Review until approval",
    "merge_wait": "Approval until merge (incl. CI)",
    "release_wait": "Merged until in production",
}


class DataError(ValueError):
    pass


def parse_ts(raw: Any) -> datetime | None:
    if raw in (None, ""):
        return None
    text = str(raw).strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError as exc:
        raise DataError(f"invalid timestamp {raw!r}") from exc
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _bool(raw: Any) -> bool:
    return str(raw).strip().lower() in ("1", "true", "yes", "y")


@dataclass(frozen=True)
class Change:
    id: str
    team: str
    size: int
    created_at: datetime
    first_review_at: datetime | None
    approved_at: datetime | None
    merged_at: datetime | None
    pipeline_seconds: int | None
    deployed_at: datetime | None
    release_id: str
    failed: bool
    restored_at: datetime | None

    @property
    def complete(self) -> bool:
        return all((self.first_review_at, self.approved_at, self.merged_at, self.deployed_at))

    def in_order(self) -> bool:
        """created <= first_review <= approved <= merged <= deployed (for the known points)."""
        points = [self.created_at, self.first_review_at, self.approved_at, self.merged_at, self.deployed_at]
        known = [p for p in points if p is not None]
        return all(a <= b for a, b in zip(known, known[1:], strict=False))


def _change(row: dict[str, Any], n: int) -> Change:
    if not row.get("id") or not row.get("created_at"):
        raise DataError(f"row {n}: 'id' and 'created_at' are required")
    try:
        return Change(
            id=str(row["id"]),
            team=str(row.get("team") or "unknown"),
            size=int(row.get("size") or 0),
            created_at=parse_ts(row["created_at"]),
            first_review_at=parse_ts(row.get("first_review_at")),
            approved_at=parse_ts(row.get("approved_at")),
            merged_at=parse_ts(row.get("merged_at")),
            pipeline_seconds=int(row["pipeline_seconds"]) if row.get("pipeline_seconds") not in (None, "") else None,
            deployed_at=parse_ts(row.get("deployed_at")),
            release_id=str(row.get("release_id") or ""),
            failed=_bool(row.get("failed", False)),
            restored_at=parse_ts(row.get("restored_at")),
        )
    except (DataError, ValueError) as exc:
        raise DataError(f"row {n}: {exc}") from exc


def load_changes(path: str | Path) -> list[Change]:
    p = Path(path)
    try:
        if p.suffix.lower() == ".csv":
            with p.open(newline="", encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
        else:
            rows = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DataError(f"cannot read {p}: {exc}") from exc
    if not isinstance(rows, list) or not rows:
        raise DataError("input must be a non-empty list of change records")
    changes = [_change(r, i) for i, r in enumerate(rows)]
    ids = [c.id for c in changes]
    if len(set(ids)) != len(ids):
        raise DataError("duplicate change ids")
    return changes
