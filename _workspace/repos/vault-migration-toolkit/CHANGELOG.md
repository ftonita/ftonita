# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning: [SemVer](https://semver.org/).

## [1.0.0] - 2026-10-08

### Added
- `inventory`: weak, shared-across-environments, duplicate, stale and unowned findings with severities.
- `plan`: deterministic legacy -> `kv-<team>/<env>/<app>/<name>` mapping; ambiguous records go to a manual queue.
- `apply`: dry-run by default, create-only writes with check-and-set, conflict detection, `--overwrite`, `--create-mounts`.
- `verify`: keyed-fingerprint comparison of source and Vault.
- Append-only ledger with no secret values; 0600 per-migration fingerprint key.
- Stdlib-only Vault HTTP client with retries; in-memory and file-backed fakes for offline demos.
- Synthetic data generator (`vault-migrate demo`).
