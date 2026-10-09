# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning: [SemVer](https://semver.org/).

## [1.0.0] - 2026-10-08

### Added
- `access.yml` schema (JSON Schema 2020-12) and typed model with group resolution.
- 11 lint rules (AAC001-AAC011): sudo ban, reference integrity, production tickets and expiries, elevated roles,
  offboarded people, expired grants, separation of duties, cross-team access, duplicates, unused objects, review window.
- `compile`: Vault HCL policies and identity groups, Kubernetes RoleBindings, GitLab member levels. Output is
  effective access as of the given date.
- `diff`: drift detection against an exported snapshot.
- `review`: expiring and elevated grants.
