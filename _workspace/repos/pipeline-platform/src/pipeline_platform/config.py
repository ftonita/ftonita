"""Defaults and derived values (image repository, placeholders)."""

from __future__ import annotations

import copy
from typing import Any

TOOL_IMAGES = {
    "kaniko": "gcr.io/kaniko-project/executor:v1.23.2-debug",
    "trivy": "aquasec/trivy:0.56.2",
    "gitleaks": "zricethezav/gitleaks:v8.21.2",
    "sonar": "sonarsource/sonar-scanner-cli:11",
    "ansible": "willhallonline/ansible:2.16-alpine-3.19",
    "helm": "alpine/k8s:1.30.4",
    "platform": "registry.example.com/platform/pipeline-platform:v1",
}


def with_defaults(cfg: dict[str, Any]) -> dict[str, Any]:
    """Return a deep copy of a validated config with defaults filled in."""
    c = copy.deepcopy(cfg)
    c["vault"].setdefault("auth_path", "jwt")
    c["vault"].setdefault("audience", c["vault"]["url"])
    reg = c["registry"]
    reg.setdefault("type", "nexus")
    reg.setdefault("layout", "path")
    reg["credentials"].setdefault("user_field", "username")
    reg["credentials"].setdefault("password_field", "password")
    build = c.setdefault("build", {})
    build.setdefault("enabled", True)
    build.setdefault("dockerfile", "Dockerfile")
    build.setdefault("context", ".")
    build.setdefault("args", {})
    quality = c.setdefault("quality", {})
    quality.setdefault("gitleaks", True)
    quality.setdefault("trivy", True)
    c["images"] = {**TOOL_IMAGES, **c.get("images", {})}
    c.setdefault("deploy", {"environments": []})
    app = c["app"]["name"]
    for env in c["deploy"]["environments"]:
        env.setdefault("approval", "auto")
        env.setdefault("secrets", {})
        sub = {"app": app, "env": env["name"]}
        if env["method"] == "helm":
            h = env["helm"]
            h["release"] = fill(h.get("release", "{app}-{env}"), **sub)
            h.setdefault("values", [])
            h.setdefault("set", {})
            h.setdefault("timeout", "5m")
        elif env["method"] == "argocd":
            a = env["argocd"]
            a.setdefault("branch", "main")
            a["values_file"] = fill(a.get("values_file", "apps/{app}/{env}/values.yaml"), **sub)
            if "sync" in a:
                a["sync"]["application"] = fill(a["sync"].get("application", "{app}-{env}"), **sub)
        elif env["method"] == "ansible":
            env["ansible"].setdefault("extra_vars", {})
    return c


def fill(template: str, **values: str) -> str:
    """Replace {app}/{env} placeholders without touching other braces."""
    for key, value in values.items():
        template = template.replace("{" + key + "}", value)
    return template


def image_repository(cfg: dict[str, Any]) -> str:
    """Image path without tag. Nexus: host/ns/app. Artifactory: path or subdomain layout."""
    reg = cfg["registry"]
    app = cfg["app"]["name"]
    ns = reg["namespace"].strip("/")
    if reg["type"] == "artifactory":
        if reg["layout"] == "subdomain":
            return f"{reg['repository']}.{reg['host']}/{ns}/{app}"
        return f"{reg['host']}/{reg['repository']}/{ns}/{app}"
    return f"{reg['host']}/{ns}/{app}"
