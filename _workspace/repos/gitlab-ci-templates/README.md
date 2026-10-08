# gitlab-ci-templates

[![ci](https://github.com/ftonita/gitlab-ci-templates/actions/workflows/ci.yml/badge.svg)](https://github.com/ftonita/gitlab-ci-templates/actions)
![GitLab CI](https://img.shields.io/badge/GitLab_CI-templates-FC6D26?logo=gitlab&logoColor=white)

A small library of reusable GitLab CI/CD building blocks: **build, test, quality gates, deploy**. A new service gets a full pipeline by `include`-ing the templates and overriding a few variables.

> Distilled from standardising delivery pipelines for 5+ product teams (new-project onboarding down to 1-2 days; ~90% of deployments automated). Sanitised, generic and free of employer code.

## Templates

| File | Jobs | Notes |
|---|---|---|
| `templates/build.yml` | `.build-image` | Kaniko: no privileged runner, no docker-in-docker. |
| `templates/test.yml` | `.test`, `.lint-yaml` | Language-agnostic; set `TEST_IMAGE` + `TEST_SCRIPT`. JUnit report artifact. |
| `templates/quality.yml` | `.sonarqube`, `.trivy-image-scan`, `.secret-scan` | SonarQube quality gate, Trivy (HIGH/CRITICAL), Gitleaks. |
| `templates/deploy.yml` | `.deploy-ansible`, `.deploy-gitops` | VM deploys through Ansible, or bump the image tag in a GitOps repo and let ArgoCD sync. |

## Usage

```yaml
include:
  - project: platform/gitlab-ci-templates
    ref: v1.0.0            # pin a tag, never a branch
    file: [templates/build.yml, templates/test.yml, templates/quality.yml, templates/deploy.yml]

build:
  extends: .build-image
trivy:
  extends: .trivy-image-scan
  needs: [build]
deploy-stage:
  extends: .deploy-gitops
  variables: { DEPLOY_ENV: stage }
```

Full example: [`examples/app.gitlab-ci.yml`](examples/app.gitlab-ci.yml).

## Design principles

1. **Hidden jobs (`.name`) only**: consumers opt in explicitly; no surprise jobs.
2. **Versioned**: consumers pin a tag, so template changes never break pipelines silently.
3. **Secrets never in YAML**: every credential is a masked CI/CD variable (or fetched from Vault).
4. **Fail early**: secret scan and image scan gate the deploy stage.

## Required CI/CD variables

`SONAR_HOST_URL`, `SONAR_TOKEN` · `SSH_PRIVATE_KEY` (Ansible deploy) · `GITOPS_REPO`, `GITOPS_TOKEN` (GitOps deploy)
