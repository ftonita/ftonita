from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples" / "consumer-app"


def load_example(name: str) -> dict:
    return yaml.safe_load((EXAMPLES / f"{name}.platform.yml").read_text(encoding="utf-8"))


@pytest.fixture
def argocd_cfg() -> dict:
    return load_example("argocd")


@pytest.fixture
def helm_cfg() -> dict:
    return load_example("helm")


@pytest.fixture
def ansible_cfg() -> dict:
    return load_example("ansible")


@pytest.fixture
def minimal_cfg() -> dict:
    return copy.deepcopy(
        {
            "version": 1,
            "app": {"name": "demo"},
            "vault": {"url": "https://vault.example.com", "role": "ci-demo"},
            "registry": {
                "host": "nexus.example.com:8082",
                "namespace": "team",
                "credentials": {"mount": "ci", "path": "nexus"},
            },
        }
    )
