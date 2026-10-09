# opsbot

[![ci](https://github.com/ftonita/opsbot/actions/workflows/ci.yml/badge.svg)](https://github.com/ftonita/opsbot/actions)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![aiogram](https://img.shields.io/badge/aiogram-3.x-2CA5E0?logo=telegram&logoColor=white)

**A ChatOps Telegram bot for on-call work that treats the chat as an attack surface:** role-based access, a two-person rule for production, rate limiting, an audit trail, and no raw secrets in code or config.

It answers "what is running and what is on fire?" from a phone, lets operators silence alerts and request deployments, and makes production changes require a second, different person with the `approver` role.

> **Synthetic data only.** Users, services, versions and alerts in the demo are fictional. The default backend is an in-memory simulation; no real system is touched unless you wire one in.

## Commands

| Command | Role | What it does |
|---|---|---|
| `/status [service]`, `/alerts`, `/deploys [service]`, `/whoami`, `/help` | viewer | Read-only views. |
| `/silence <alert> <30m\|2h> <reason>` | operator | Silences a **currently firing** alert for 1 min - 8 h (configurable), reason required. |
| `/deploy <service> <env> <tag>` | operator | Does not deploy. Issues a 6-character code. |
| `/confirm <code>` | operator / approver | Non-prod: only the requester confirms. **Prod: someone else, with role `approver`.** |
| `/cancel <code>` | operator | Cancel your pending request (admins can cancel any). |
| `/audit [n]` | admin | Last audit entries. |

## A session (replayed offline against the synthetic backend)

`opsbot replay examples/opsbot.yml examples/demo-session.txt` runs a transcript without Telegram:

```text
> carol: /silence HighErrorRate 1h flaky
  Permission denied: /silence needs role 'operator' (you are 'viewer').
> alice: /silence HighErrorRate 1h deploying fix, tracked in INC-42
  Silenced HighErrorRate for 1h (silence-001).
> alice: /deploy orders-api stage 7c1d9e22
  Requested: deploy orders-api to stage as 7c1d9e22.
  Run /confirm AAAAAA within 120s to proceed.
> alice: /confirm AAAAAA
  Done: orders-api stage now runs 7c1d9e22.
> alice: /deploy orders-api prod 7c1d9e22
  Production change requested: deploy orders-api to prod as 7c1d9e22.
  Another person with role 'approver' must run /confirm BBBBBB within 120s.
> alice: /confirm BBBBBB
  Denied: production changes need a second person. Ask an approver.
> bob: /confirm BBBBBB
  Done: orders-api prod now runs 7c1d9e22.
> 999: /status
  Access denied.
```

(Codes are fixed with `--codes` so the output is reproducible; in real use they are random.)

## Security design

| Threat | Mitigation |
|---|---|
| Anyone who finds the bot | Allowlist of numeric Telegram user IDs; strangers get one generic line and an audit entry, then silence once they exceed the rate limit. |
| Stolen or misused operator account | Production needs a second person with a higher role; codes are single-use, expire (120 s by default) and are not burned by an unauthorised attempt. |
| Typos and fat fingers | Services and environments are validated against the config; tags match a strict pattern; deploying the version that already runs is a no-op; silences only apply to firing alerts. |
| Injection through chat text | No shell, no `eval`; replies are plain text (`parse_mode=None`) so `<b>` or Markdown in an alert reason is never interpreted; audit arguments are stripped of control characters and truncated. |
| Flooding | Per-user token bucket (burst 5, 20/min by default). |
| Leaking internals | Backend exceptions are reduced to the exception class in the audit log; users see a generic message. |
| Secrets | The bot token is read from `TELEGRAM_BOT_TOKEN` only; the container runs as non-root, read-only, with all capabilities dropped. |
| Groups | Ignored unless the chat ID is listed in `allowed_chats`. |

## Run it

```bash
pip install .
opsbot check-config examples/opsbot.yml
export TELEGRAM_BOT_TOKEN=...            # from @BotFather; never put it in a file
opsbot run examples/opsbot.yml --audit-file audit.jsonl
# real alerts and silences instead of the simulation:
opsbot run examples/opsbot.yml --alertmanager https://alertmanager.internal.example
```

or `docker compose up --build` with `TELEGRAM_BOT_TOKEN` in your environment.

Architecture: `core.OpsBot.handle(user_id, text)` contains every decision and knows nothing about Telegram; `telegram_app.py` only moves text in and out. Backends implement a small protocol (`statuses`, `alerts`, `silence`, `deploys`, `deploy`), so a Prometheus, GitLab or Argo CD adapter is one class.

## What is verified

Reproduce with `pip install -e ".[dev]" && pytest` (62 tests, 97% line coverage):

- Every command, role gate, validation error and confirmation path, including the two-person rule, expiry, single use and "an unauthorised attempt does not burn the code".
- Rate limiting, audit sanitisation, backend-failure handling without leakage.
- The Telegram adapter runs through **aiogram's real `Dispatcher`** with a recording session: replies are plain text, strangers are denied, groups ignored, HTML is not interpreted.
- The Alertmanager client runs over real HTTP against a **stub of the v2 API written for these tests**.
- The replay output is deterministic.

**Not verified:** a live Telegram bot (no token or network access to Telegram was available), a real Alertmanager, long-polling behaviour, `docker build` / `docker compose`, and any real deployment backend (only the synthetic one exists). Users are identified by Telegram ID, so the security of the setup rests on Telegram account security (enable 2FA); the bot cannot defend against a hijacked account of an approver.
