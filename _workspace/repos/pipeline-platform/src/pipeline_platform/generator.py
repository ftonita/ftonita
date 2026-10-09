"""Turn a validated .platform.yml plus a pipeline context into a GitLab child pipeline."""

from __future__ import annotations

import fnmatch
import re
import shlex
from typing import Any

import yaml

from . import __version__
from .config import image_repository, with_defaults
from .context import Context

STAGES = ["test", "build", "scan", "deploy"]


def _vault_ref(ref: dict[str, str], *, file: bool = False, field: str | None = None) -> dict[str, Any]:
    """GitLab-native `secrets:` entry that authenticates with $VAULT_ID_TOKEN."""
    entry: dict[str, Any] = {
        "vault": {
            "engine": {"name": "kv-v2", "path": ref["mount"]},
            "path": ref["path"],
            "field": field or ref["field"],
        },
        "token": "$VAULT_ID_TOKEN",
    }
    if file:
        entry["file"] = True
    return entry


def _with_vault(cfg: dict[str, Any], secrets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """id_tokens + secrets block for a job. Empty when the job needs no secrets."""
    if not secrets:
        return {}
    return {
        "id_tokens": {"VAULT_ID_TOKEN": {"aud": cfg["vault"]["audience"]}},
        "secrets": secrets,
    }


def _registry_secrets(cfg: dict[str, Any]) -> dict[str, dict[str, Any]]:
    cred = cfg["registry"]["credentials"]
    return {
        "REGISTRY_USER": _vault_ref(cred, field=cred["user_field"]),
        "REGISTRY_PASSWORD": _vault_ref(cred, field=cred["password_field"]),
    }


def env_matches(env: dict[str, Any], ctx: Context) -> bool:
    """Does this pipeline context trigger a deployment to `env`?"""
    on = env["refs"]
    if ctx.kind == "branch":
        return any(fnmatch.fnmatchcase(ctx.branch, p) for p in on.get("branches", []))
    if ctx.kind == "tag" and "tags" in on:
        return re.search(on["tags"], ctx.tag) is not None
    return False


def _plan(cfg: dict[str, Any], ctx: Context) -> dict[str, Any]:
    """Decide which jobs exist for this context. Pure function, easy to test."""
    envs = [e for e in cfg["deploy"]["environments"] if env_matches(e, ctx)]
    on_default = ctx.kind == "branch" and ctx.branch == ctx.default_branch
    publish = cfg["build"]["enabled"] and (ctx.kind == "tag" or on_default or bool(envs))
    return {
        "envs": envs,
        "test": "test" in cfg and ctx.kind != "other",
        "gitleaks": cfg["quality"]["gitleaks"] and ctx.kind in ("merge_request", "branch", "tag"),
        "sonar": "sonarqube" in cfg["quality"] and (ctx.kind == "merge_request" or on_default),
        "build": cfg["build"]["enabled"] and (ctx.kind == "merge_request" or publish),
        "publish": publish,
        "trivy": publish and cfg["quality"]["trivy"],
    }


def _test_job(cfg: dict[str, Any]) -> dict[str, Any]:
    t = cfg["test"]
    job: dict[str, Any] = {
        "stage": "test",
        "image": t["image"],
        "script": list(t["script"]),
        "interruptible": True,
    }
    if t.get("junit"):
        job["artifacts"] = {"when": "always", "reports": {"junit": t["junit"]}, "expire_in": "1 week"}
    return job


def _gitleaks_job(cfg: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage": "test",
        "image": {"name": cfg["images"]["gitleaks"], "entrypoint": [""]},
        "script": ["gitleaks detect --source . --redact --verbose"],
        "interruptible": True,
    }


def _sonar_job(cfg: dict[str, Any]) -> dict[str, Any]:
    s = cfg["quality"]["sonarqube"]
    job = {
        "stage": "test",
        "image": {"name": cfg["images"]["sonar"], "entrypoint": [""]},
        "variables": {"GIT_DEPTH": "0", "SONAR_USER_HOME": "$CI_PROJECT_DIR/.sonar"},
        "script": [
            'sonar-scanner -Dsonar.projectKey="$CI_PROJECT_PATH_SLUG"'
            f" -Dsonar.host.url={shlex.quote(s['host_url'])} -Dsonar.qualitygate.wait=true"
        ],
        "cache": {"key": "sonar", "paths": [".sonar/cache"]},
    }
    job.update(_with_vault(cfg, {"SONAR_TOKEN": _vault_ref(s["token"])}))
    return job


def _build_job(cfg: dict[str, Any], *, push: bool, ctx: Context) -> dict[str, Any]:
    b = cfg["build"]
    dest = ['--destination "$IMAGE"']
    if ctx.kind == "tag":
        dest.append('--destination "$IMAGE_REPOSITORY:$CI_COMMIT_TAG"')
    cmd = [
        "/kaniko/executor",
        f"--context {shlex.quote(b['context'])}",
        f"--dockerfile {shlex.quote(b['dockerfile'])}",
        *(dest if push else ["--no-push"]),
        "--cache=true",
        *(f"--build-arg {shlex.quote(f'{k}={v}')}" for k, v in sorted(b["args"].items())),
    ]
    job: dict[str, Any] = {
        "stage": "build",
        "image": {"name": cfg["images"]["kaniko"], "entrypoint": [""]},
        "script": [
            "mkdir -p /kaniko/.docker",
            "AUTH=$(printf '%s:%s' \"$REGISTRY_USER\" \"$REGISTRY_PASSWORD\" | base64 | tr -d '\\n')\n"
            'printf \'{"auths":{"%s":{"auth":"%s"}}}\' "$REGISTRY_HOST" "$AUTH"'
            " > /kaniko/.docker/config.json",
            " ".join(cmd),
        ],
    }
    job.update(_with_vault(cfg, _registry_secrets(cfg)))
    return job


def _trivy_job(cfg: dict[str, Any]) -> dict[str, Any]:
    job: dict[str, Any] = {
        "stage": "scan",
        "image": {"name": cfg["images"]["trivy"], "entrypoint": [""]},
        "needs": ["build"],
        "script": [
            'export TRIVY_USERNAME="$REGISTRY_USER" TRIVY_PASSWORD="$REGISTRY_PASSWORD"',
            'trivy image --exit-code 1 --severity HIGH,CRITICAL --ignore-unfixed "$IMAGE"',
        ],
    }
    job.update(_with_vault(cfg, _registry_secrets(cfg)))
    return job


def _deploy_job(cfg: dict[str, Any], env: dict[str, Any], needs: list[str]) -> dict[str, Any]:
    method = env["method"]
    secrets = {name: _vault_ref(ref) for name, ref in sorted(env["secrets"].items())}
    if method == "ansible":
        job = _deploy_ansible(cfg, env, secrets)
    elif method == "helm":
        job = _deploy_helm(cfg, env, secrets)
    else:
        job = _deploy_argocd(cfg, env, secrets)
    job["stage"] = "deploy"
    if needs:
        job["needs"] = needs
    job["environment"] = {"name": env["name"]}
    job["resource_group"] = f"{cfg['app']['name']}-{env['name']}"
    if env["approval"] == "manual":
        job["when"] = "manual"
        job["allow_failure"] = False
    return job


def _deploy_ansible(cfg: dict[str, Any], env: dict[str, Any], secrets: dict[str, Any]) -> dict[str, Any]:
    a = env["ansible"]
    secrets["SSH_PRIVATE_KEY"] = _vault_ref(a["ssh_key"], file=True)
    extra = [f"-e {shlex.quote(f'{k}={v}')}" for k, v in sorted(a["extra_vars"].items())]
    cmd = [
        "ansible-playbook",
        "-i",
        shlex.quote(a["inventory"]),
        shlex.quote(a["playbook"]),
        '--private-key "$SSH_PRIVATE_KEY"',
        '-e "image=$IMAGE"',
        '-e "image_tag=$IMAGE_TAG"',
        *extra,
    ]
    job = {
        "image": cfg["images"]["ansible"],
        "variables": {"ANSIBLE_HOST_KEY_CHECKING": "false", "DEPLOY_ENV": env["name"]},
        "script": ['chmod 600 "$SSH_PRIVATE_KEY"', " ".join(cmd)],
    }
    job.update(_with_vault(cfg, secrets))
    return job


def _deploy_helm(cfg: dict[str, Any], env: dict[str, Any], secrets: dict[str, Any]) -> dict[str, Any]:
    h = env["helm"]
    secrets["KUBECONFIG"] = _vault_ref(h["kubeconfig"], file=True)
    cmd = [
        "helm upgrade --install",
        shlex.quote(h["release"]),
        shlex.quote(h["chart"]),
        "--namespace",
        shlex.quote(h["namespace"]),
        "--create-namespace",
        "--atomic",
        "--timeout",
        h["timeout"],
        '--set "image.repository=$IMAGE_REPOSITORY"',
        '--set "image.tag=$IMAGE_TAG"',
        *(f"-f {shlex.quote(v)}" for v in h["values"]),
        *(f"--set {shlex.quote(f'{k}={v}')}" for k, v in sorted(h["set"].items())),
    ]
    job = {"image": {"name": cfg["images"]["helm"], "entrypoint": [""]}, "script": [" ".join(cmd)]}
    job.update(_with_vault(cfg, secrets))
    return job


def _deploy_argocd(cfg: dict[str, Any], env: dict[str, Any], secrets: dict[str, Any]) -> dict[str, Any]:
    a = env["argocd"]
    secrets["GITOPS_TOKEN"] = _vault_ref(a["credentials"])
    repo = shlex.quote(a["gitops_repo"])
    branch = shlex.quote(a["branch"])
    vf = shlex.quote(a["values_file"])
    script = [
        "git config --global user.name pipeline-platform\n"
        "git config --global user.email pipeline-platform@users.noreply.invalid",
        f"git clone --depth 1 --branch {branch} "
        f"\"https://oauth2:${{GITOPS_TOKEN}}@\"$(printf '%s' {repo} | sed 's#^https://##') gitops",
        "cd gitops",
        f'pipeline-platform bump-tag --file {vf} --tag "$IMAGE_TAG"',
        "git add -A\n"
        "if git diff --cached --quiet; then echo 'values already at this tag'; exit 0; fi\n"
        f'git commit -m "deploy {cfg["app"]["name"]} {env["name"]}: $IMAGE_TAG"\n'
        f"for i in 1 2 3; do git push origin HEAD:{branch} && break; "
        f"git pull --rebase origin {branch}; done",
    ]
    if "sync" in a:
        s = a["sync"]
        secrets["ARGOCD_AUTH_TOKEN"] = _vault_ref(s["token"])
        app = shlex.quote(s["application"])
        script += [
            f"export ARGOCD_SERVER={shlex.quote(s['server'])}",
            f"argocd app wait {app} --health --sync --timeout 300 --grpc-web",
        ]
    job = {"image": cfg["images"]["platform"], "script": script}
    job.update(_with_vault(cfg, secrets))
    return job


def generate(raw_cfg: dict[str, Any], ctx: Context) -> dict[str, Any]:
    """Build the child pipeline as a dict. Input must already be validated."""
    cfg = with_defaults(raw_cfg)
    plan = _plan(cfg, ctx)
    jobs: dict[str, Any] = {}
    if plan["test"]:
        jobs["test"] = _test_job(cfg)
    if plan["gitleaks"]:
        jobs["gitleaks"] = _gitleaks_job(cfg)
    if plan["sonar"]:
        jobs["sonarqube"] = _sonar_job(cfg)
    if plan["build"]:
        jobs["build"] = _build_job(cfg, push=plan["publish"], ctx=ctx)
    if plan["trivy"]:
        jobs["trivy"] = _trivy_job(cfg)
    deploy_needs = [n for n in ("build", "trivy") if n in jobs]
    for env in plan["envs"]:
        jobs[f"deploy:{env['name']}"] = _deploy_job(cfg, env, deploy_needs)
    if not jobs:
        jobs["noop"] = {
            "stage": "test",
            "image": "busybox:1.36",
            "script": ["echo 'nothing to do for this ref'"],
        }
    reg = cfg["registry"]
    pipeline: dict[str, Any] = {
        "stages": [s for s in STAGES if any(j.get("stage") == s for j in jobs.values())],
        "variables": {
            "IMAGE_REPOSITORY": image_repository(cfg),
            "IMAGE_TAG": "$CI_COMMIT_SHORT_SHA",
            "IMAGE": "$IMAGE_REPOSITORY:$IMAGE_TAG",
            "REGISTRY_HOST": reg["host"],
            "VAULT_SERVER_URL": cfg["vault"]["url"],
            "VAULT_AUTH_ROLE": cfg["vault"]["role"],
            "VAULT_AUTH_PATH": cfg["vault"]["auth_path"],
        },
    }
    pipeline.update(jobs)
    return pipeline


def _str_representer(dumper: yaml.SafeDumper, data: str) -> yaml.ScalarNode:
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


class _Dumper(yaml.SafeDumper):
    pass


_Dumper.add_representer(str, _str_representer)


def dump(pipeline: dict[str, Any]) -> str:
    """Deterministic YAML (insertion order, block scalars for multi-line scripts)."""
    header = f"# Generated by pipeline-platform {__version__} from .platform.yml. Do not edit.\n"
    return header + yaml.dump(pipeline, Dumper=_Dumper, sort_keys=False, width=120)
