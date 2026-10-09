# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning: [SemVer](https://semver.org/).

## [1.0.0] - 2026-10-09

### Added
- Four-stage lead-time breakdown (first-review wait, review, approval-to-merge, merge-to-production) with mean / p50 / p90 and share.
- DORA-style metrics: deployment frequency, lead time, change failure rate, time to restore.
- Batching analysis (changes per deployment, deploy-day concentration), per-team and PR-size breakdowns.
- Wall-clock or working-hours (Mon-Fri 09-18, configurable UTC offset) time accounting.
- Rule-based recommendations with a what-if estimate; `simulate` and `compare` commands.
- Markdown, JSON and SVG outputs; synthetic before/after dataset generator; dependency-free runtime.
