"""Shared helpers for golden-file tests (also used by scripts/update_golden.py)."""

from __future__ import annotations

from pathlib import Path

import yaml

from pipeline_platform.context import Context
from pipeline_platform.generator import dump, generate

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples" / "consumer-app"
EXPECTED = EXAMPLES / "expected"

VARIANTS = ["argocd", "helm", "ansible"]
CONTEXTS = {
    "main": {"CI_COMMIT_BRANCH": "main", "CI_DEFAULT_BRANCH": "main", "CI_PIPELINE_SOURCE": "push"},
    "mr": {
        "CI_MERGE_REQUEST_IID": "12",
        "CI_MERGE_REQUEST_SOURCE_BRANCH_NAME": "feat/x",
        "CI_PIPELINE_SOURCE": "merge_request_event",
        "CI_DEFAULT_BRANCH": "main",
    },
    "tag": {"CI_COMMIT_TAG": "v1.4.0", "CI_DEFAULT_BRANCH": "main", "CI_PIPELINE_SOURCE": "push"},
    "feature": {"CI_COMMIT_BRANCH": "feat/x", "CI_DEFAULT_BRANCH": "main", "CI_PIPELINE_SOURCE": "push"},
}


def golden_path(variant: str, ctx_name: str) -> Path:
    return EXPECTED / f"{variant}.{ctx_name}.yml"


def render(variant: str, ctx_name: str) -> str:
    cfg = yaml.safe_load((EXAMPLES / f"{variant}.platform.yml").read_text(encoding="utf-8"))
    return dump(generate(cfg, Context.from_env(CONTEXTS[ctx_name])))
