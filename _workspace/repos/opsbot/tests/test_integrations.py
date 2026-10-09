from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.methods import SendMessage
from aiogram.types import Chat, Update, User
from aiogram.types import Message as TgMessage

from opsbot.alertmanager import AlertmanagerClient, AlertmanagerError
from opsbot.backends import SyntheticBackend
from opsbot.cli import HybridBackend, main
from opsbot.telegram_app import build_dispatcher


# ---- Alertmanager over real HTTP (stub) -----------------------------------------------------------
class AMState:
    silences: list[dict] = []
    fail = False


@pytest.fixture
def am():
    state = AMState()
    state.silences = []

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body):
            raw = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):  # noqa: N802
            if state.fail:
                return self._send(500, {})
            self._send(
                200,
                [
                    {
                        "labels": {"alertname": "HighErrorRate", "service": "orders-api", "severity": "critical"},
                        "annotations": {"summary": "5xx high"},
                        "status": {"silencedBy": ["s1"]},
                    },
                    {"labels": {"alertname": "Disk"}, "annotations": {}, "status": {"silencedBy": []}},
                ],
            )

        def do_POST(self):  # noqa: N802
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            state.silences.append(body)
            self._send(200, {"silenceID": "abc-123"})

    server = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield state, AlertmanagerClient(f"http://127.0.0.1:{server.server_address[1]}")
    server.shutdown()


def test_alertmanager_alerts_and_silence(am):
    state, client = am
    a, b = client.alerts()
    assert (a.name, a.silenced, a.severity) == ("HighErrorRate", True, "critical") and (b.silenced, b.service) == (
        False,
        "-",
    )
    sid = client.silence("HighErrorRate", timedelta(hours=1), "alice via opsbot", "fixing")
    sent = state.silences[0]
    assert (
        sid == "abc-123" and sent["matchers"][0]["value"] == "HighErrorRate" and sent["createdBy"] == "alice via opsbot"
    )
    start, end = (datetime.fromisoformat(sent[k]) for k in ("startsAt", "endsAt"))
    assert end - start == timedelta(hours=1)


def test_alertmanager_errors_are_wrapped(am):
    state, client = am
    state.fail = True
    with pytest.raises(AlertmanagerError, match="HTTP 500"):
        client.alerts()
    with pytest.raises(AlertmanagerError, match="unreachable"):
        AlertmanagerClient("http://127.0.0.1:9", timeout=0.3).alerts()
    with pytest.raises(AlertmanagerError, match="https"):
        AlertmanagerClient("http://alertmanager.example.com")


def test_hybrid_backend_uses_alertmanager_for_alerts_only(am):
    _, client = am
    hybrid = HybridBackend(SyntheticBackend.demo(datetime(2026, 10, 9, tzinfo=timezone.utc)), client)
    assert [a.name for a in hybrid.alerts()] == ["HighErrorRate", "Disk"]
    assert hybrid.statuses("orders-api")  # still synthetic
    assert hybrid.silence("Disk", timedelta(minutes=5), "x", "y") == "abc-123"


# ---- Telegram wiring through aiogram's real dispatcher with a recording session -------------------
class RecordingSession(BaseSession):
    def __init__(self):
        super().__init__()
        self.sent: list[SendMessage] = []

    async def close(self):
        pass

    async def stream_content(self, *a, **k):  # pragma: no cover
        yield b""

    async def make_request(self, bot, method, timeout=None):
        self.sent.append(method)
        return TgMessage(
            message_id=1,
            date=datetime.now(timezone.utc),
            chat=Chat(id=method.chat_id, type="private"),
            text=method.text,
        )


def update(text, user_id, chat_id=None, chat_type="private", uid=1):
    return Update(
        update_id=uid,
        message=TgMessage(
            message_id=uid,
            date=datetime.now(timezone.utc),
            chat=Chat(id=chat_id or user_id, type=chat_type),
            from_user=User(id=user_id, is_bot=False, first_name="x"),
            text=text,
        ),
    )


async def feed(core, *updates):
    session = RecordingSession()
    bot = Bot(token="123456:TEST-TOKEN-NOT-REAL", session=session)
    dp = build_dispatcher(core)
    for u in updates:
        await dp.feed_update(bot, u)
    return session.sent


async def test_telegram_roundtrip_replies_in_plain_text(bot):
    sent = await feed(bot, update("/whoami", 3))
    assert [m.text for m in sent] == ["carol, role: viewer"] and sent[0].parse_mode is None and sent[0].chat_id == 3


async def test_telegram_denies_strangers_and_ignores_plain_chat(bot):
    sent = await feed(bot, update("/status", 999, uid=1), update("good morning", 1, uid=2))
    assert [m.text for m in sent] == ["Access denied."]


async def test_telegram_ignores_groups_unless_allowed(bot, cfg):
    assert await feed(bot, update("/whoami", 1, chat_id=-100, chat_type="group")) == []
    object.__setattr__(cfg, "allowed_chats", (-100,))
    sent = await feed(bot, update("/whoami", 1, chat_id=-100, chat_type="group"))
    assert [m.text for m in sent] == ["alice, role: operator"]


async def test_telegram_html_in_user_input_is_not_interpreted(bot):
    sent = await feed(bot, update("/status <b>x</b>", 3))
    assert "<b>x</b>" in sent[0].text and sent[0].parse_mode is None


# ---- CLI ----------------------------------------------------------------------------------------
def test_cli_check_and_replay_are_reproducible(capsys):
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent / "examples"
    assert main(["check-config", str(root / "opsbot.yml")]) == 0
    capsys.readouterr()
    args = ["replay", str(root / "opsbot.yml"), str(root / "demo-session.txt"), "--codes", "AAAAAA,BBBBBB"]
    assert main(args) == 0
    out = capsys.readouterr().out
    assert "Permission denied: /silence needs role 'operator'" in out
    assert "second person" in out and "Done: orders-api prod now runs 7c1d9e22." in out and "Access denied." in out
    assert main(args) == 0 and capsys.readouterr().out == out


def test_cli_run_requires_token_and_config_errors(monkeypatch, tmp_path, capsys):
    from pathlib import Path

    example = str(Path(__file__).resolve().parent.parent / "examples" / "opsbot.yml")
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    assert main(["run", example]) == 2
    assert "TELEGRAM_BOT_TOKEN" in capsys.readouterr().err
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "x")
    assert main(["run", str(tmp_path / "nope.yml")]) == 2
