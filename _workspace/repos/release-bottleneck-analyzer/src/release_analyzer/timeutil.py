"""Wall-clock vs working-time durations. Waiting over a weekend is not the same as a slow review."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class Calendar:
    """Mon-Fri, [start_hour, end_hour) in a fixed UTC offset. `None` calendar means wall clock."""

    start_hour: int = 9
    end_hour: int = 18
    utc_offset_hours: float = 0

    def working_seconds(self, start: datetime, end: datetime) -> float:
        if end <= start:
            return 0.0
        tz = timezone(timedelta(hours=self.utc_offset_hours))
        s, e = start.astimezone(tz), end.astimezone(tz)
        total = 0.0
        day = s.replace(hour=0, minute=0, second=0, microsecond=0)
        while day <= e:
            if day.weekday() < 5:
                lo = max(s, day.replace(hour=self.start_hour))
                hi = min(e, day.replace(hour=self.end_hour))
                if hi > lo:
                    total += (hi - lo).total_seconds()
            day += timedelta(days=1)
        return total


def seconds_between(start: datetime, end: datetime, cal: Calendar | None) -> float:
    return max((end - start).total_seconds(), 0.0) if cal is None else cal.working_seconds(start, end)
