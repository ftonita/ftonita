"""Small, dependency-free statistics (linear-interpolation percentiles, like numpy's default)."""

from __future__ import annotations

import math
from collections.abc import Sequence


def percentile(values: Sequence[float], q: float) -> float:
    if not values:
        raise ValueError("percentile of empty data")
    if not 0 <= q <= 100:
        raise ValueError("q must be within 0..100")
    xs = sorted(values)
    pos = (len(xs) - 1) * q / 100
    lo, hi = math.floor(pos), math.ceil(pos)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def median(values: Sequence[float]) -> float:
    return percentile(values, 50)


def mean(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("mean of empty data")
    return sum(values) / len(values)
