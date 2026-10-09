"""Regenerate examples/consumer-app/expected/*.yml. Review the diff before committing."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

from golden import CONTEXTS, VARIANTS, golden_path, render  # noqa: E402

for variant in VARIANTS:
    for ctx_name in CONTEXTS:
        path = golden_path(variant, ctx_name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render(variant, ctx_name), encoding="utf-8")
        print("wrote", path.relative_to(ROOT))
