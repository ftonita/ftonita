from __future__ import annotations

import copy

import pytest

from pipeline_platform.schema import validate, validate_schema


def paths(issues):
    return [str(i) for i in issues]


@pytest.mark.parametrize("name", ["argocd", "helm", "ansible"])
def test_examples_are_valid(name):
    from conftest import load_example

    assert validate(load_example(name)) == []


def test_minimal_config_is_valid(minimal_cfg):
    assert validate(minimal_cfg) == []


@pytest.mark.parametrize("key", ["version", "app", "vault", "registry"])
def test_required_top_level_keys(minimal_cfg, key):
    del minimal_cfg[key]
    assert any(key in m for m in paths(validate(minimal_cfg)))


def test_wrong_version_rejected(minimal_cfg):
    minimal_cfg["version"] = 2
    assert validate(minimal_cfg)


def test_unknown_key_rejected(minimal_cfg):
    minimal_cfg["surprise"] = True
    assert any("surprise" in m for m in paths(validate(minimal_cfg)))


def test_non_mapping_document_rejected():
    assert validate(["not", "a", "mapping"])
    assert validate(None)


def test_vault_url_must_be_https(minimal_cfg):
    minimal_cfg["vault"]["url"] = "http://vault.example.com"
    assert any(i.path == "vault.url" for i in validate(minimal_cfg))


@pytest.mark.parametrize("name", ["Bad_Name", "-lead", "trail-", "UPPER", ""])
def test_app_name_pattern(minimal_cfg, name):
    minimal_cfg["app"]["name"] = name
    assert any(i.path == "app.name" for i in validate(minimal_cfg))


def test_artifactory_requires_repository(minimal_cfg):
    minimal_cfg["registry"]["type"] = "artifactory"
    issues = validate(minimal_cfg)
    assert any("repository" in i.message for i in issues)
    minimal_cfg["registry"]["repository"] = "docker-local"
    assert validate(minimal_cfg) == []


def test_unknown_registry_type(minimal_cfg):
    minimal_cfg["registry"]["type"] = "harbor"
    assert validate(minimal_cfg)


def test_secret_ref_needs_all_fields(argocd_cfg):
    del argocd_cfg["quality"]["sonarqube"]["token"]["field"]
    assert any("field" in i.message for i in validate(argocd_cfg))


def test_env_var_name_pattern(ansible_cfg):
    ansible_cfg["deploy"]["environments"][0]["secrets"]["lower_case"] = {
        "mount": "apps",
        "path": "x",
        "field": "y",
    }
    assert validate(ansible_cfg)


@pytest.mark.parametrize(
    ("method", "foreign"),
    [("helm", "ansible"), ("ansible", "helm"), ("argocd", "helm")],
)
def test_method_must_match_config_block(argocd_cfg, helm_cfg, ansible_cfg, method, foreign):
    cfgs = {"argocd": argocd_cfg, "helm": helm_cfg, "ansible": ansible_cfg}
    donor = {"ansible": ansible_cfg, "helm": helm_cfg}[foreign]["deploy"]["environments"][0][foreign]
    cfg = copy.deepcopy(cfgs[method])
    env = cfg["deploy"]["environments"][0]
    env[foreign] = donor
    assert validate_schema(cfg), "foreign block alongside the real one must be rejected"


def test_method_without_its_block(helm_cfg):
    del helm_cfg["deploy"]["environments"][0]["helm"]
    assert any("helm" in i.message for i in validate(helm_cfg))


def test_refs_required_and_nonempty(helm_cfg):
    env = helm_cfg["deploy"]["environments"][0]
    env["refs"] = {}
    assert validate(helm_cfg)
    del env["refs"]
    assert any("refs" in i.message for i in validate(helm_cfg))


def test_yaml_boolean_key_trap_is_reported(helm_cfg):
    # YAML 1.1 parses an unquoted `on:` key as boolean True. The schema must not accept it.
    env = helm_cfg["deploy"]["environments"][0]
    env[True] = env.pop("refs")
    assert validate_schema(helm_cfg)


def test_duplicate_environment_names(argocd_cfg):
    envs = argocd_cfg["deploy"]["environments"]
    envs[1]["name"] = envs[0]["name"]
    assert any("duplicate" in i.message for i in validate(argocd_cfg))


def test_invalid_tag_regex(argocd_cfg):
    argocd_cfg["deploy"]["environments"][2]["refs"]["tags"] = "([unclosed"
    assert any("invalid regex" in i.message for i in validate(argocd_cfg))


def test_empty_environment_list_rejected(argocd_cfg):
    argocd_cfg["deploy"]["environments"] = []
    assert validate(argocd_cfg)


def test_issue_paths_are_readable(argocd_cfg):
    del argocd_cfg["deploy"]["environments"][1]["argocd"]["gitops_repo"]
    issues = validate(argocd_cfg)
    assert any(i.path == "deploy.environments[1].argocd" for i in issues)
