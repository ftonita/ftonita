# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/). The config schema version (`version: 1` in
`.platform.yml`) always equals the major version of the platform.

## [Unreleased]

## [1.0.0] - 2026-10-08

### Added
- `.platform.yml` (schema v1) as the single per-repository configuration, validated with JSON Schema
  and readable, path-annotated error messages.
- Dynamic child pipeline: `pipeline.yml` generates `child-pipeline.yml` for the current ref and runs it
  with `trigger:include:artifact`. Jobs are included by condition (merge request, default branch,
  feature branch, tag) at generation time.
- Vault access through GitLab `id_tokens` and native `secrets:` (no static Vault token).
- Kaniko image build tagged with the commit SHA (`$CI_COMMIT_SHORT_SHA`), pushed to Nexus; Artifactory
  as an option (`path` and `subdomain` layouts). Extra release tag on tag pipelines.
- Quality gates: Gitleaks, SonarQube, Trivy.
- Deploy methods per environment: Ansible, Helm, ArgoCD (GitOps commit via `bump-tag`, optional sync wait).
- `pipeline-platform` CLI: `validate`, `generate`, `bump-tag`, `schema`.
- `examples/consumer-app` (three variants with golden outputs) and `examples/gitops-repo`.
- Unit tests, golden-file tests and validation of every generated pipeline against GitLab's CI schema.

### Notes
- Moving tag `v1` always points to the latest `1.x.y`; pin `v1.x.y` for fully reproducible pipelines.
- Breaking changes to the config or generated pipeline will ship as `v2` with a new schema file.
