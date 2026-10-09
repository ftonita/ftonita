# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning: [SemVer](https://semver.org/).

## [1.0.0] - 2026-10-09

### Added
- Commands: `/status`, `/alerts`, `/deploys`, `/silence`, `/deploy`, `/confirm`, `/cancel`, `/audit`, `/help`, `/whoami`.
- Roles (viewer < operator < approver < admin) from an allowlist; unknown users get a generic denial.
- Two-person rule for production changes; single-use, expiring confirmation codes.
- Per-user token-bucket rate limiting; JSONL audit trail with sanitised arguments.
- Alertmanager API v2 client; synthetic backend; transcript replay; aiogram 3 adapter; Dockerfile and compose file.
