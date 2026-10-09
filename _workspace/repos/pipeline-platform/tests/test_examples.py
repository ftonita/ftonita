"""Golden files: the generated pipelines for every example and context are reviewed in Git."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from golden import CONTEXTS, VARIANTS, golden_path, render
from pipeline_platform.gitops import bump_image_tag

GITOPS = Path(__file__).resolve().parent.parent / "examples" / "gitops-repo"


@pytest.mark.parametrize("ctx", CONTEXTS)
@pytest.mark.parametrize("variant", VARIANTS)
def test_generated_pipeline_matches_golden(variant, ctx):
    expected = golden_path(variant, ctx).read_text(encoding="utf-8")
    assert render(variant, ctx) == expected, "run `python scripts/update_golden.py` and review the diff"


@pytest.mark.parametrize("env", ["dev", "stage", "prod"])
def test_gitops_example_values_are_bumpable(env):
    text = (GITOPS / "apps" / "orders-api" / env / "values.yaml").read_text(encoding="utf-8")
    assert yaml.safe_load(bump_image_tag(text, "cafe1234"))["image"]["tag"] == "cafe1234"


def test_applicationset_layout_matches_values_path_used_by_the_argocd_method():
    # The default values_file is apps/{app}/{env}/values.yaml; the ApplicationSet scans apps/*/*.
    appset = yaml.safe_load((GITOPS / "argocd" / "applicationset.yaml").read_text(encoding="utf-8"))
    assert appset["spec"]["generators"][0]["git"]["directories"][0]["path"] == "apps/*/*"
    for env in ("dev", "stage", "prod"):
        assert (GITOPS / "apps" / "orders-api" / env / "values.yaml").is_file()


def test_entrypoint_pipeline_is_valid_yaml_with_dynamic_child():
    doc = yaml.safe_load((Path(__file__).resolve().parent.parent / "pipeline.yml").read_text("utf-8"))
    inc = doc["platform:run"]["trigger"]["include"][0]
    assert inc == {"artifact": "child-pipeline.yml", "job": "platform:generate"}
