from __future__ import annotations

import copy

import pytest

from pipeline_platform.context import Context
from pipeline_platform.generator import dump, env_matches, generate

MAIN = Context("branch", branch="main", default_branch="main")
FEATURE = Context("branch", branch="feat/x", default_branch="main")
MR = Context("merge_request", branch="feat/x", default_branch="main")
TAG = Context("tag", tag="v1.4.0", default_branch="main")
OTHER = Context("other")


def jobs(pipeline):
    reserved = {"stages", "variables"}
    return {k: v for k, v in pipeline.items() if k not in reserved}


# ---- which jobs exist -------------------------------------------------------------------------


def test_default_branch_builds_scans_and_deploys_to_matching_envs(argocd_cfg):
    p = generate(argocd_cfg, MAIN)
    assert set(jobs(p)) == {"test", "gitleaks", "sonarqube", "build", "trivy", "deploy:dev", "deploy:stage"}
    assert p["stages"] == ["test", "build", "scan", "deploy"]


def test_merge_request_verifies_but_never_publishes_or_deploys(argocd_cfg):
    p = generate(argocd_cfg, MR)
    assert set(jobs(p)) == {"test", "gitleaks", "sonarqube", "build"}
    build_cmd = p["build"]["script"][-1]
    assert "--no-push" in build_cmd and "--destination" not in build_cmd


def test_tag_matching_regex_deploys_to_prod_only(argocd_cfg):
    p = generate(argocd_cfg, TAG)
    deploys = [k for k in jobs(p) if k.startswith("deploy:")]
    assert deploys == ["deploy:prod"]
    assert '--destination "$IMAGE_REPOSITORY:$CI_COMMIT_TAG"' in p["build"]["script"][-1]


def test_tag_not_matching_regex_still_publishes_but_does_not_deploy(argocd_cfg):
    p = generate(argocd_cfg, Context("tag", tag="nightly-2026", default_branch="main"))
    assert "build" in p and not any(k.startswith("deploy:") for k in p)


def test_feature_branch_runs_only_cheap_checks(argocd_cfg):
    assert set(jobs(generate(argocd_cfg, FEATURE))) == {"test", "gitleaks"}


def test_unknown_context_yields_noop_pipeline(argocd_cfg):
    p = generate(argocd_cfg, OTHER)
    assert list(jobs(p)) == ["noop"]  # an empty child pipeline would fail in GitLab


def test_glob_branch_patterns(helm_cfg):
    p = generate(helm_cfg, Context("branch", branch="release/2.1", default_branch="main"))
    assert "deploy:stage" in p and "build" in p and "trivy" in p


def test_build_disabled_removes_build_and_trivy(argocd_cfg):
    argocd_cfg["build"] = {"enabled": False}
    assert not {"build", "trivy"} & set(generate(argocd_cfg, MAIN))


def test_trivy_can_be_disabled(ansible_cfg):
    assert "trivy" not in generate(ansible_cfg, TAG)


def test_without_test_section_no_test_job(minimal_cfg):
    assert "test" not in generate(minimal_cfg, MAIN)


def test_env_matches_never_true_for_merge_requests(argocd_cfg):
    env = argocd_cfg["deploy"]["environments"][0]
    assert env_matches(env, MAIN) and not env_matches(env, MR)


# ---- image tag from commit SHA, registry layouts ------------------------------------------------


def test_image_is_tagged_with_commit_sha(argocd_cfg):
    v = generate(argocd_cfg, MAIN)["variables"]
    assert v["IMAGE_TAG"] == "$CI_COMMIT_SHORT_SHA"
    assert v["IMAGE"] == "$IMAGE_REPOSITORY:$IMAGE_TAG"
    assert v["IMAGE_REPOSITORY"] == "nexus.example.com:8082/shop/orders-api"


def test_artifactory_path_layout(helm_cfg):
    assert generate(helm_cfg, MAIN)["variables"]["IMAGE_REPOSITORY"] == (
        "artifactory.example.com/docker-local/finance/billing-worker"
    )


def test_artifactory_subdomain_layout(helm_cfg):
    helm_cfg["registry"]["layout"] = "subdomain"
    assert generate(helm_cfg, MAIN)["variables"]["IMAGE_REPOSITORY"] == (
        "docker-local.artifactory.example.com/finance/billing-worker"
    )


def test_registry_credentials_use_configured_fields(helm_cfg):
    s = generate(helm_cfg, MAIN)["build"]["secrets"]
    assert s["REGISTRY_USER"]["vault"]["field"] == "user"
    assert s["REGISTRY_PASSWORD"]["vault"]["field"] == "token"


def test_build_args_are_shell_quoted(minimal_cfg):
    minimal_cfg["build"] = {"args": {"MSG": "hello world; rm -rf /"}}
    cmd = generate(minimal_cfg, MAIN)["build"]["script"][-1]
    assert "--build-arg 'MSG=hello world; rm -rf /'" in cmd


# ---- Vault via GitLab id_tokens -----------------------------------------------------------------


def test_jobs_with_secrets_get_id_token_and_native_vault_secrets(argocd_cfg):
    p = generate(argocd_cfg, MAIN)
    for name in ("build", "trivy", "sonarqube", "deploy:dev"):
        job = p[name]
        assert job["id_tokens"] == {"VAULT_ID_TOKEN": {"aud": "https://vault.example.com"}}
        for secret in job["secrets"].values():
            assert secret["token"] == "$VAULT_ID_TOKEN"
            assert secret["vault"]["engine"]["name"] == "kv-v2"


def test_jobs_without_secrets_get_no_vault_wiring(argocd_cfg):
    p = generate(argocd_cfg, MAIN)
    for name in ("test", "gitleaks"):
        assert "id_tokens" not in p[name] and "secrets" not in p[name]


def test_custom_audience_is_used(minimal_cfg):
    minimal_cfg["vault"]["audience"] = "vault-ci"
    minimal_cfg["deploy"] = {"environments": []}
    assert generate(minimal_cfg, MAIN)["build"]["id_tokens"]["VAULT_ID_TOKEN"]["aud"] == "vault-ci"


def test_vault_connection_variables(argocd_cfg):
    v = generate(argocd_cfg, MAIN)["variables"]
    assert (v["VAULT_SERVER_URL"], v["VAULT_AUTH_ROLE"], v["VAULT_AUTH_PATH"]) == (
        "https://vault.example.com",
        "ci-orders-api",
        "jwt",
    )


@pytest.mark.parametrize("variant", ["argocd_cfg", "helm_cfg", "ansible_cfg"])
@pytest.mark.parametrize("ctx", [MAIN, MR, TAG])
def test_no_static_tokens_every_secret_is_a_vault_reference(request, variant, ctx):
    pipeline = generate(request.getfixturevalue(variant), ctx)
    assert "VAULT_TOKEN" not in dump(pipeline)
    for name, job in jobs(pipeline).items():
        for env_name, secret in job.get("secrets", {}).items():
            assert set(secret) <= {"vault", "token", "file"}, (name, env_name)
            assert secret["token"] == "$VAULT_ID_TOKEN", (name, env_name)
        assert ("secrets" in job) == ("id_tokens" in job), name


def test_file_secrets_are_marked_as_files(helm_cfg, ansible_cfg):
    assert generate(helm_cfg, MAIN)["deploy:stage"]["secrets"]["KUBECONFIG"]["file"] is True
    assert generate(ansible_cfg, TAG)["deploy:prod"]["secrets"]["SSH_PRIVATE_KEY"]["file"] is True


def test_extra_env_secrets_are_injected(ansible_cfg):
    s = generate(ansible_cfg, TAG)["deploy:prod"]["secrets"]
    assert s["DB_PASSWORD"]["vault"]["path"] == "legacy-gateway/prod"


# ---- deploy methods -----------------------------------------------------------------------------


def test_ansible_deploy(ansible_cfg):
    job = generate(ansible_cfg, TAG)["deploy:prod"]
    assert job["image"].startswith("willhallonline/ansible")
    cmd = job["script"][-1]
    assert cmd.startswith("ansible-playbook -i deploy/inventories/prod deploy/site.yml")
    assert '-e "image_tag=$IMAGE_TAG"' in cmd and "-e service_name=legacy-gateway" in cmd
    assert job["script"][0] == 'chmod 600 "$SSH_PRIVATE_KEY"'


def test_helm_deploy(helm_cfg):
    cmd = generate(helm_cfg, MAIN)["deploy:stage"]["script"][0]
    assert cmd.startswith("helm upgrade --install billing-worker-stage ./deploy/chart")
    for part in (
        "--namespace billing-stage",
        "--atomic",
        "--timeout 5m",
        '--set "image.tag=$IMAGE_TAG"',
        "-f deploy/values-stage.yaml",
        "--set replicaCount=2",
    ):
        assert part in cmd


def test_argocd_deploy_bumps_tag_in_gitops_repo(argocd_cfg):
    script = "\n".join(generate(argocd_cfg, MAIN)["deploy:dev"]["script"])
    assert "git clone --depth 1 --branch main" in script
    assert 'pipeline-platform bump-tag --file apps/orders-api/dev/values.yaml --tag "$IMAGE_TAG"' in script
    assert "argocd app wait" not in script  # dev relies on auto-sync


def test_argocd_prod_waits_for_sync(argocd_cfg):
    job = generate(argocd_cfg, TAG)["deploy:prod"]
    script = "\n".join(job["script"])
    assert "argocd app wait orders-api-prod --health --sync" in script
    assert "ARGOCD_AUTH_TOKEN" in job["secrets"] and "GITOPS_TOKEN" in job["secrets"]


def test_argocd_commit_is_skipped_when_nothing_changed(argocd_cfg):
    assert "git diff --cached --quiet" in "\n".join(generate(argocd_cfg, MAIN)["deploy:dev"]["script"])


# ---- deploy job controls ------------------------------------------------------------------------


def test_manual_approval_blocks_the_job(argocd_cfg):
    p = generate(argocd_cfg, MAIN)
    assert "when" not in p["deploy:dev"]
    assert p["deploy:stage"]["when"] == "manual" and p["deploy:stage"]["allow_failure"] is False


def test_deploy_needs_build_and_scan(argocd_cfg):
    assert generate(argocd_cfg, MAIN)["deploy:dev"]["needs"] == ["build", "trivy"]


def test_environment_and_resource_group(argocd_cfg):
    job = generate(argocd_cfg, MAIN)["deploy:dev"]
    assert job["environment"] == {"name": "dev"} and job["resource_group"] == "orders-api-dev"


def test_tool_images_can_be_overridden(argocd_cfg):
    argocd_cfg["images"] = {"kaniko": "mirror.example.com/kaniko:1"}
    p = generate(argocd_cfg, MAIN)
    assert p["build"]["image"]["name"] == "mirror.example.com/kaniko:1"
    assert p["trivy"]["image"]["name"].startswith("aquasec/trivy")


# ---- purity and output --------------------------------------------------------------------------


def test_input_is_not_mutated(argocd_cfg):
    before = copy.deepcopy(argocd_cfg)
    generate(argocd_cfg, MAIN)
    assert argocd_cfg == before


def test_output_is_deterministic(argocd_cfg):
    assert dump(generate(argocd_cfg, MAIN)) == dump(generate(copy.deepcopy(argocd_cfg), MAIN))


def test_dump_uses_block_scalars_and_header(argocd_cfg):
    text = dump(generate(argocd_cfg, MAIN))
    assert text.startswith("# Generated by pipeline-platform 1.0.0")
    assert "- |-" in text
