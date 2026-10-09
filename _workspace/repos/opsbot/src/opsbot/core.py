"""Transport-independent command handling: authorisation, validation, rate limiting, confirmation, audit."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .audit import AuditLog, clean
from .backends import Backend
from .config import Config, User
from .confirm import Confirmations
from .ratelimit import RateLimiter

TAG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
ALERT_RE = re.compile(r"^[A-Za-z0-9_:.-]{1,64}$")
DURATION_RE = re.compile(r"^(\d{1,3})([mh])$")
READ_ONLY = {"help", "whoami", "status", "alerts", "deploys", "audit"}


class UserError(ValueError):
    """A problem the user can fix; the message is shown to them."""


@dataclass(frozen=True)
class Command:
    name: str
    role: str
    usage: str
    summary: str
    handler: Callable[..., str]


class OpsBot:
    def __init__(
        self,
        cfg: Config,
        backend: Backend,
        audit: AuditLog | None = None,
        clock: Callable[[], datetime] | None = None,
        code_rng: Callable[[int], str] | None = None,
    ) -> None:
        self.cfg, self.backend = cfg, backend
        self.audit = audit or AuditLog()
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.limiter = RateLimiter(cfg.rate_burst, cfg.rate_per_minute)
        self.confirmations = Confirmations(cfg.confirm_ttl_seconds, code_rng)
        self.commands = {
            c.name: c
            for c in (
                Command("help", "viewer", "/help", "list commands you may use", self._help),
                Command("whoami", "viewer", "/whoami", "show your role", self._whoami),
                Command("status", "viewer", "/status [service]", "versions and health per environment", self._status),
                Command("alerts", "viewer", "/alerts", "currently firing alerts", self._alerts),
                Command("deploys", "viewer", "/deploys [service]", "recent deployments", self._deploys),
                Command(
                    "silence", "operator", "/silence <alert> <30m|2h> <reason>", "silence a firing alert", self._silence
                ),
                Command(
                    "deploy",
                    "operator",
                    "/deploy <service> <env> <tag>",
                    "request a deployment (needs /confirm)",
                    self._deploy,
                ),
                Command("confirm", "operator", "/confirm <code>", "confirm a pending action", self._confirm),
                Command("cancel", "operator", "/cancel <code>", "cancel your pending action", self._cancel),
                Command("audit", "admin", "/audit [n]", "last audit entries", self._audit),
            )
        }

    # ---- entry point ------------------------------------------------------------------------------
    def handle(self, user_id: int, text: str, *, private: bool = True) -> str | None:
        """Return the reply text, or None when the bot should stay silent."""
        text = (text or "").strip()
        if not text.startswith("/"):
            return None
        parts = text.split()
        name = parts[0][1:].split("@")[0].lower()
        args = parts[1:]
        now = self.clock()
        user = self.cfg.users.get(user_id)
        label = user.name if user else f"unknown:{user_id}"
        if not self.limiter.allow(user_id, now):
            self.audit.record(now, user_id, label, name, " ".join(args), "rate_limited")
            return "Too many requests, slow down." if user else None
        if user is None:
            self.audit.record(now, user_id, label, name, "", "denied", "not in allowlist")
            return "Access denied."
        cmd = self.commands.get(name)
        if cmd is None:
            return "Unknown command. Try /help."
        if not user.at_least(cmd.role):
            self.audit.record(now, user_id, user.name, name, " ".join(args), "denied", f"needs role {cmd.role}")
            return f"Permission denied: /{name} needs role '{cmd.role}' (you are '{user.role}')."
        try:
            reply = cmd.handler(user, args, now)
        except UserError as exc:
            self.audit.record(now, user_id, user.name, name, " ".join(args), "invalid", str(exc))
            return f"{exc}\nUsage: {cmd.usage}"
        except Exception as exc:  # noqa: BLE001 - never leak internals to the chat
            self.audit.record(now, user_id, user.name, name, " ".join(args), "error", type(exc).__name__)
            return "Something went wrong talking to a backend. The incident is in the audit log."
        if name in READ_ONLY:  # state-changing commands record their own outcome with details
            self.audit.record(now, user_id, user.name, name, " ".join(args), "ok")
        return reply

    # ---- helpers ----------------------------------------------------------------------------------
    def _service(self, raw: str) -> str:
        if raw not in self.cfg.services:
            raise UserError(f"Unknown service '{clean(raw, 40)}'. Known: {', '.join(self.cfg.services)}.")
        return raw

    def _env(self, raw: str) -> str:
        if raw not in self.cfg.environments:
            raise UserError(f"Unknown environment '{clean(raw, 40)}'. Known: {', '.join(self.cfg.environments)}.")
        return raw

    def _log(self, now: datetime, user: User, cmd: str, args: str, outcome: str, detail: str = "") -> None:
        self.audit.record(now, user.id, user.name, cmd, args, outcome, detail)

    # ---- read-only commands -----------------------------------------------------------------------
    def _help(self, user: User, args: list[str], now: datetime) -> str:
        lines = [f"/{c.usage[1:]}  - {c.summary}" for c in self.commands.values() if user.at_least(c.role)]
        return "Commands for your role:\n" + "\n".join(lines)

    def _whoami(self, user: User, args: list[str], now: datetime) -> str:
        return f"{user.name}, role: {user.role}"

    def _status(self, user: User, args: list[str], now: datetime) -> str:
        service = self._service(args[0]) if args else None
        rows = self.backend.statuses(service)
        if not rows:
            return "No data."
        return "\n".join(
            f"{'OK  ' if r.healthy else 'FAIL'} {r.service}/{r.env} {r.version}{' - ' + r.detail if r.detail else ''}"
            for r in rows
        )

    def _alerts(self, user: User, args: list[str], now: datetime) -> str:
        alerts = self.backend.alerts()
        if not alerts:
            return "No firing alerts."
        return "\n".join(
            f"[{a.severity}] {a.name} ({a.service}){' [silenced]' if a.silenced else ''}: {a.summary}" for a in alerts
        )

    def _deploys(self, user: User, args: list[str], now: datetime) -> str:
        service = self._service(args[0]) if args else None
        rows = self.backend.deploys(service, 5)
        if not rows:
            return "No deployments."
        return "\n".join(
            f"{d.at:%m-%d %H:%M} {d.service}/{d.env} {d.version} by {d.by} {'ok' if d.ok else 'FAILED'}" for d in rows
        )

    def _audit(self, user: User, args: list[str], now: datetime) -> str:
        try:
            n = int(args[0]) if args else 10
        except ValueError as exc:
            raise UserError("n must be a number") from exc
        rows = self.audit.tail(max(1, min(n, 30)))
        return (
            "\n".join(
                f"{e.at[11:19]} {e.user} /{e.command} {e.outcome}" + (f" ({e.detail})" if e.detail else "")
                for e in rows
            )
            or "Audit log is empty."
        )

    # ---- state-changing commands ------------------------------------------------------------------
    def _silence(self, user: User, args: list[str], now: datetime) -> str:
        if len(args) < 3:
            raise UserError("Need an alert name, a duration and a reason.")
        name, dur, reason = args[0], args[1], clean(" ".join(args[2:]), 200).strip()
        if not ALERT_RE.match(name):
            raise UserError("Invalid alert name.")
        m = DURATION_RE.match(dur)
        if not m:
            raise UserError("Duration must look like 30m or 2h.")
        delta = timedelta(minutes=int(m[1])) if m[2] == "m" else timedelta(hours=int(m[1]))
        if not timedelta(minutes=1) <= delta <= timedelta(hours=self.cfg.max_silence_hours):
            raise UserError(f"Duration must be between 1m and {self.cfg.max_silence_hours}h.")
        if len(reason) < 3:
            raise UserError("A reason of at least 3 characters is required.")
        if name not in {a.name for a in self.backend.alerts()}:
            raise UserError(f"'{name}' is not firing right now.")
        sid = self.backend.silence(name, delta, f"{user.name} via opsbot", reason)
        self._log(now, user, "silence", f"{name} {dur}", "ok", f"{sid}: {reason}")
        return f"Silenced {name} for {dur} ({sid})."

    def _deploy(self, user: User, args: list[str], now: datetime) -> str:
        if len(args) != 3:
            raise UserError("Need a service, an environment and a tag.")
        service, env, tag = self._service(args[0]), self._env(args[1]), args[2]
        if not TAG_RE.match(tag):
            raise UserError("Invalid tag (letters, digits, '.', '_', '-'; max 64).")
        running = {(s.service, s.env): s.version for s in self.backend.statuses(service)}
        if running.get((service, env)) == tag:
            return f"{service}/{env} already runs {tag}. Nothing to do."
        prod = env in self.cfg.prod_environments
        desc = f"deploy {service} to {env} as {tag}"

        def action() -> str:
            return self.backend.deploy(service, env, tag, user.name, self.clock())

        p = self.confirmations.create(user.id, desc, action, now, needs_other=prod)
        self._log(now, user, "deploy", f"{service} {env} {tag}", "pending", f"code issued, prod={prod}")
        if prod:
            return (
                f"Production change requested: {desc}.\nAnother person with role 'approver' must run "
                f"/confirm {p.code} within {self.cfg.confirm_ttl_seconds}s."
            )
        return f"Requested: {desc}.\nRun /confirm {p.code} within {self.cfg.confirm_ttl_seconds}s to proceed."

    def _confirm(self, user: User, args: list[str], now: datetime) -> str:
        if len(args) != 1:
            raise UserError("Need the confirmation code.")
        p = self.confirmations.peek(args[0], now)
        if p is None:
            raise UserError("Unknown or expired code.")
        if p.needs_other:
            if p.requester_id == user.id:
                self._log(now, user, "confirm", p.code, "denied", "self-approval of production change")
                return "Denied: production changes need a second person. Ask an approver."
            if not user.at_least("approver"):
                self._log(now, user, "confirm", p.code, "denied", "confirmer is not an approver")
                return "Denied: only an 'approver' can confirm production changes."
        elif p.requester_id != user.id:
            self._log(now, user, "confirm", p.code, "denied", "not the requester")
            return "Denied: only the requester can confirm this action."
        self.confirmations.take(p.code, now)
        requester = self.cfg.users[p.requester_id].name
        try:
            result = p.action()
        except Exception as exc:  # noqa: BLE001
            self._log(now, user, "confirm", p.code, "error", f"{p.description}: {type(exc).__name__}")
            return "The action failed. Details are in the audit log."
        self._log(now, user, "confirm", p.code, "ok", f"{p.description}; requested by {requester}")
        return f"Done: {result}."

    def _cancel(self, user: User, args: list[str], now: datetime) -> str:
        if len(args) != 1:
            raise UserError("Need the confirmation code.")
        p = self.confirmations.peek(args[0], now)
        if p is None or (p.requester_id != user.id and not user.at_least("admin")):
            raise UserError("Unknown code, or it is not yours.")
        self.confirmations.take(p.code, now)
        self._log(now, user, "cancel", p.code, "ok", p.description)
        return "Cancelled."
