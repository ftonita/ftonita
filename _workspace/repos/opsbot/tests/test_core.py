from __future__ import annotations

import pytest

ALICE, BOB, CAROL, DAVE, ERIN, STRANGER = 1, 2, 3, 4, 5, 999


def last_outcomes(audit, n=1):
    return [e.outcome for e in audit.entries[-n:]]


# ---- access control -----------------------------------------------------------------------------


def test_non_commands_get_no_reply(bot):
    assert bot.handle(ALICE, "hello") is None and bot.handle(ALICE, "") is None


def test_unknown_user_is_denied_without_information_and_audited(bot, audit):
    assert bot.handle(STRANGER, "/status") == "Access denied."
    assert bot.handle(STRANGER, "/help") == "Access denied."
    e = audit.entries[0]
    assert (e.outcome, e.detail, e.user) == ("denied", "not in allowlist", "unknown:999")


def test_unknown_user_flood_goes_silent(bot):
    replies = [bot.handle(STRANGER, "/status") for _ in range(8)]
    assert replies[:5] == ["Access denied."] * 5 and replies[5:] == [None] * 3


@pytest.mark.parametrize(
    ("user", "cmd"),
    [(CAROL, "/silence A 1h reason"), (CAROL, "/deploy orders-api dev x"), (ALICE, "/audit"), (BOB, "/audit")],
)
def test_role_gates(bot, audit, user, cmd):
    assert bot.handle(user, cmd).startswith("Permission denied")
    assert last_outcomes(audit) == ["denied"]


def test_help_only_lists_commands_for_the_role(bot):
    viewer, admin = bot.handle(CAROL, "/help"), bot.handle(DAVE, "/help")
    assert "/silence" not in viewer and "/status" in viewer and "/audit" in admin and "/silence" in admin


def test_command_with_bot_suffix_and_case(bot):
    assert bot.handle(CAROL, "/WhoAmI@my_ops_bot") == "carol, role: viewer"


def test_unknown_command(bot):
    assert "Unknown command" in bot.handle(ALICE, "/rm -rf")


# ---- read-only ----------------------------------------------------------------------------------


def test_status_alerts_deploys(bot):
    assert "FAIL billing-worker/stage" in bot.handle(CAROL, "/status")
    assert bot.handle(CAROL, "/status orders-api").count("\n") == 2
    assert "[critical] HighErrorRate" in bot.handle(CAROL, "/alerts")
    assert "by ci-bot" in bot.handle(CAROL, "/deploys orders-api")


def test_unknown_service_is_rejected_with_usage(bot):
    r = bot.handle(CAROL, "/status payroll")
    assert "Unknown service" in r and "Usage: /status [service]" in r


# ---- silence ------------------------------------------------------------------------------------


def test_silence_happy_path_marks_alert_and_audits_reason(bot, audit, backend):
    assert bot.handle(ALICE, "/silence HighErrorRate 90m deploying hotfix INC-42").startswith("Silenced HighErrorRate")
    assert "[silenced]" in bot.handle(CAROL, "/alerts")
    e = audit.entries[0]
    assert e.command == "silence" and e.outcome == "ok" and "INC-42" in e.detail
    assert backend.silences[0][3] == "deploying hotfix INC-42"


@pytest.mark.parametrize(
    ("args", "fragment"),
    [
        ("HighErrorRate", "Need an alert name"),
        ("High!Rate 1h why", "Invalid alert name"),
        ("HighErrorRate 5d why", "Duration must look like"),
        ("HighErrorRate 0m why", "between 1m and 8h"),
        ("HighErrorRate 9h why", "between 1m and 8h"),
        ("HighErrorRate 1h x", "reason of at least 3"),
        ("NotFiring 1h whatever", "not firing"),
    ],
)
def test_silence_validation(bot, audit, args, fragment):
    assert fragment in bot.handle(ALICE, f"/silence {args}")
    assert last_outcomes(audit) == ["invalid"]


def test_silence_reason_is_sanitised_in_audit(bot, audit):
    bot.handle(ALICE, "/silence HighErrorRate 1h <b>bold</b>\x07 ok")
    assert "\x07" not in audit.entries[0].detail


# ---- deploy / confirm ---------------------------------------------------------------------------


def test_non_prod_deploy_requires_requesters_own_confirmation(bot, backend):
    r = bot.handle(ALICE, "/deploy orders-api stage 7c1d9e22")
    assert "Run /confirm AAAAAA" in r and backend.versions[("orders-api", "stage")] == "a1b2c3d4"
    assert bot.handle(ALICE, "/confirm aaaaaa") == "Done: orders-api stage now runs 7c1d9e22."
    assert backend.versions[("orders-api", "stage")] == "7c1d9e22"


def test_confirmation_is_single_use(bot):
    bot.handle(ALICE, "/deploy orders-api dev abc")
    bot.handle(ALICE, "/confirm AAAAAA")
    assert "Unknown or expired" in bot.handle(ALICE, "/confirm AAAAAA")


def test_other_operator_cannot_confirm_your_non_prod_change(bot, backend):
    bot.handle(ALICE, "/deploy orders-api dev abc")
    assert "only the requester" in bot.handle(ERIN, "/confirm AAAAAA")
    assert backend.versions[("orders-api", "dev")] == "ffee0011"
    assert "Done" in bot.handle(ALICE, "/confirm AAAAAA")  # the failed attempt did not burn the code


def test_prod_change_needs_a_second_person_with_approver_role(bot, backend, audit):
    r = bot.handle(ALICE, "/deploy orders-api prod abc")
    assert "approver" in r and "Production" in r
    assert "second person" in bot.handle(ALICE, "/confirm AAAAAA")
    assert "only an 'approver'" in bot.handle(ERIN, "/confirm AAAAAA")
    assert backend.versions[("orders-api", "prod")] == "a1b2c3d4"
    assert bot.handle(BOB, "/confirm AAAAAA") == "Done: orders-api prod now runs abc."
    assert [e.outcome for e in audit.entries if e.command == "confirm"] == ["denied", "denied", "ok"]
    assert "requested by alice" in audit.entries[-1].detail and audit.entries[-1].user == "bob"


def test_approver_cannot_approve_their_own_prod_request(bot):
    bot.handle(BOB, "/deploy orders-api prod abc")
    assert "second person" in bot.handle(BOB, "/confirm AAAAAA")


def test_confirmation_expires(bot, clock):
    bot.handle(ALICE, "/deploy orders-api dev abc")
    clock.advance(121)
    assert "Unknown or expired" in bot.handle(ALICE, "/confirm AAAAAA")


def test_cancel_by_owner_or_admin_only(bot):
    bot.handle(ALICE, "/deploy orders-api dev abc")
    assert "not yours" in bot.handle(ERIN, "/cancel AAAAAA")
    assert bot.handle(ALICE, "/cancel AAAAAA") == "Cancelled."
    bot.handle(ALICE, "/deploy orders-api dev abc")
    assert bot.handle(DAVE, "/cancel BBBBBB") == "Cancelled."
    assert "Unknown or expired" in bot.handle(ALICE, "/confirm BBBBBB")


@pytest.mark.parametrize(
    ("args", "fragment"),
    [
        ("orders-api dev", "Need a service"),
        ("payroll dev abc", "Unknown service"),
        ("orders-api qa abc", "Unknown environment"),
        ("orders-api dev $(reboot)", "Invalid tag"),
        ("orders-api dev ../../x", "Invalid tag"),
        ("orders-api dev " + "a" * 65, "Invalid tag"),
    ],
)
def test_deploy_validation(bot, args, fragment):
    assert fragment in bot.handle(ALICE, f"/deploy {args}")
    assert len(bot.confirmations) == 0


def test_deploying_the_running_version_is_a_no_op(bot):
    assert "already runs" in bot.handle(ALICE, "/deploy orders-api prod a1b2c3d4")
    assert len(bot.confirmations) == 0


def test_backend_failure_is_not_leaked(bot, audit, backend):
    def boom(*a, **k):
        raise RuntimeError("password=hunter2 connection string")

    backend.statuses = boom
    reply = bot.handle(CAROL, "/status")
    assert "hunter2" not in reply and "backend" in reply
    assert audit.entries[-1].outcome == "error" and audit.entries[-1].detail == "RuntimeError"


def test_failed_action_is_reported_and_audited(bot, audit, backend):
    bot.handle(ALICE, "/deploy orders-api dev abc")

    def boom(*a, **k):
        raise RuntimeError("token=secret")

    backend.deploy = boom
    reply = bot.handle(ALICE, "/confirm AAAAAA")
    assert "failed" in reply and "secret" not in reply
    assert audit.entries[-1].outcome == "error"


# ---- rate limiting and audit command ------------------------------------------------------------


def test_rate_limit_applies_per_user_and_recovers(bot, clock, audit):
    replies = [bot.handle(CAROL, "/whoami") for _ in range(7)]
    assert replies[5] == "Too many requests, slow down." and "rate_limited" in {e.outcome for e in audit.entries}
    assert bot.handle(ALICE, "/whoami")  # others unaffected
    clock.advance(30)
    assert bot.handle(CAROL, "/whoami") == "carol, role: viewer"


def test_audit_command_for_admins(bot):
    bot.handle(ALICE, "/silence HighErrorRate 1h reason here")
    out = bot.handle(DAVE, "/audit 5")
    assert "alice /silence ok" in out
    assert "n must be a number" in bot.handle(DAVE, "/audit many")
