"""Alertmanager API v2 client (stdlib only). Used for alerts and silences; deploys stay behind your own Deployer."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from .backends import Alert


class AlertmanagerError(RuntimeError):
    pass


class AlertmanagerClient:
    def __init__(self, base_url: str, timeout: float = 5.0) -> None:
        if not base_url.startswith(("https://", "http://127.0.0.1", "http://localhost")):
            raise AlertmanagerError("use https for non-local Alertmanager URLs")
        self.base, self.timeout = base_url.rstrip("/"), timeout

    def _call(self, method: str, path: str, body: dict | None = None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            f"{self.base}{path}", data=data, method=method, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310 - scheme checked above
                return json.loads(resp.read() or b"null")
        except urllib.error.HTTPError as exc:
            raise AlertmanagerError(f"Alertmanager returned HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise AlertmanagerError("Alertmanager is unreachable") from exc

    def alerts(self) -> list[Alert]:
        out = []
        for a in self._call("GET", "/api/v2/alerts?active=true") or []:
            labels, ann = a.get("labels", {}), a.get("annotations", {})
            out.append(
                Alert(
                    labels.get("alertname", "unknown"),
                    labels.get("service", "-"),
                    labels.get("severity", "none"),
                    ann.get("summary", ""),
                    bool(a.get("status", {}).get("silencedBy")),
                )
            )
        return out

    def silence(self, alert_name: str, duration: timedelta, author: str, reason: str) -> str:
        now = datetime.now(timezone.utc)
        res = self._call(
            "POST",
            "/api/v2/silences",
            {
                "matchers": [{"name": "alertname", "value": alert_name, "isRegex": False, "isEqual": True}],
                "startsAt": now.isoformat(),
                "endsAt": (now + duration).isoformat(),
                "createdBy": author,
                "comment": reason,
            },
        )
        return str(res["silenceID"])
