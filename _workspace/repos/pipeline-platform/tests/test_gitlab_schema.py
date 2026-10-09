"""Validate generated pipelines against GitLab's official CI JSON Schema.

The schema is not vendored. Point GITLAB_CI_SCHEMA at a local copy of
https://gitlab.com/gitlab-org/gitlab/-/raw/master/app/assets/javascripts/editor/schema/ci.json
to run these tests; they are skipped otherwise.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft7Validator

from golden import CONTEXTS, VARIANTS, render

SCHEMA_PATH = os.environ.get("GITLAB_CI_SCHEMA", "")
pytestmark = pytest.mark.skipif(not Path(SCHEMA_PATH).is_file(), reason="GITLAB_CI_SCHEMA not set")


@pytest.fixture(scope="module")
def validator():
    return Draft7Validator(json.loads(Path(SCHEMA_PATH).read_text(encoding="utf-8")))


def errors(validator, doc):
    return [f"{list(e.absolute_path)}: {e.message[:200]}" for e in validator.iter_errors(doc)]


@pytest.mark.parametrize("ctx", CONTEXTS)
@pytest.mark.parametrize("variant", VARIANTS)
def test_generated_pipeline_is_valid_gitlab_ci(validator, variant, ctx):
    assert errors(validator, yaml.safe_load(render(variant, ctx))) == []


def test_entrypoint_pipeline_is_valid_gitlab_ci(validator):
    doc = yaml.safe_load((Path(__file__).resolve().parent.parent / "pipeline.yml").read_text("utf-8"))
    assert errors(validator, doc) == []


def test_consumer_gitlab_ci_is_valid(validator):
    path = Path(__file__).resolve().parent.parent / "examples" / "consumer-app" / ".gitlab-ci.yml"
    assert errors(validator, yaml.safe_load(path.read_text("utf-8"))) == []
