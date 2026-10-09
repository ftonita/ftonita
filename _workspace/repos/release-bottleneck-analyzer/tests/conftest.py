from __future__ import annotations

from datetime import datetime, timezone

import pytest

from release_analyzer.demo import build
from release_analyzer.model import Change, parse_ts

UTC = timezone.utc


def ts(day: int, hour: int, minute: int = 0) -> datetime:
    """March 2026: the 2nd is a Monday."""
    return datetime(2026, 3, day, hour, minute, tzinfo=UTC)


def change(
    i="C1",
    team="t",
    size=10,
    created=None,
    first=None,
    approved=None,
    merged=None,
    deployed=None,
    release_id="",
    failed=False,
    restored=None,
    pipeline=600,
) -> Change:
    return Change(
        i,
        team,
        size,
        created or ts(2, 9),
        first or ts(2, 11),
        approved or ts(2, 15),
        merged or ts(2, 16),
        pipeline,
        deployed or ts(3, 16),
        release_id,
        failed,
        restored,
    )


@pytest.fixture
def before_rows():
    return build("before")


@pytest.fixture
def after_rows():
    return build("after")


def to_changes(rows):
    from release_analyzer.model import _change

    return [_change(r, i) for i, r in enumerate(rows)]


@pytest.fixture
def before(before_rows):
    return to_changes(before_rows)


@pytest.fixture
def after(after_rows):
    return to_changes(after_rows)


__all__ = ["change", "ts", "parse_ts", "to_changes"]
