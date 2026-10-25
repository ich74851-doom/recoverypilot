from __future__ import annotations

from datetime import UTC, datetime, timedelta

from recoverypilot.config import ClientPolicy, Settings
from recoverypilot.engine import build_context, triage
from recoverypilot.models import JobStatus, Priority, Severity
from recoverypilot.parsers import load_records
from recoverypilot.rules import JobContext
from recoverypilot.scoring import priority_for, score_finding
from tests.conftest import make_run

NOW = datetime(2026, 10, 20, 8, 0, tzinfo=UTC)


def test_context_streak_and_last_success() -> None:
    history = [
        make_run(status=JobStatus.SUCCESS, ended_at=NOW - timedelta(hours=50)),
        make_run(status=JobStatus.FAILED, ended_at=NOW - timedelta(hours=26)),
        make_run(status=JobStatus.FAILED, ended_at=NOW - timedelta(hours=2)),
    ]
    ctx = build_context(history, NOW, rpo_hours=24)
    assert ctx.consecutive_failures == 2
    assert ctx.hours_since_success == 50
    assert ctx.rpo_breached


def test_warning_counts_as_restore_point() -> None:
    ctx = build_context([make_run(status=JobStatus.WARNING, ended_at=NOW)], NOW, 24)
    assert ctx.hours_since_success == 0
    assert not ctx.rpo_breached


def test_unknown_last_success_is_not_assumed_breached() -> None:
    ctx = build_context([make_run(status=JobStatus.FAILED)], NOW, 24)
    assert ctx.hours_since_success is None
    assert not ctx.rpo_breached


def test_exported_last_success_field_is_used() -> None:
    run = make_run(last_success_at=NOW - timedelta(hours=30))
    assert build_context([run], NOW, 24).rpo_breached


def test_scoring_breakdown_is_explainable() -> None:
    ctx = JobContext(
        consecutive_failures=3, hours_since_success=72, rpo_hours=24, rpo_breached=True
    )
    score, parts = score_finding(Severity.HIGH, ctx, tier=1)
    factors = {p.factor: p.points for p in parts}
    assert factors == {"severity": 55, "rpo_breach": 20, "failure_streak": 10, "client_tier": 10}
    assert score == 95


def test_score_is_capped_at_100() -> None:
    ctx = JobContext(
        consecutive_failures=10, hours_since_success=999, rpo_hours=1, rpo_breached=True
    )
    assert score_finding(Severity.CRITICAL, ctx, tier=1)[0] == 100


def test_priority_bands() -> None:
    t = Settings().priority_thresholds
    assert [priority_for(s, t) for s in (95, 80, 79, 60, 40, 39, 0)] == [
        Priority.P1,
        Priority.P1,
        Priority.P2,
        Priority.P2,
        Priority.P3,
        Priority.P4,
        Priority.P4,
    ]


def test_healthy_jobs_produce_no_findings() -> None:
    report = triage([make_run(status=JobStatus.SUCCESS, ended_at=NOW)], as_of=NOW)
    assert report.findings == []
    assert report.summary.healthy_jobs == 1


def test_unmatched_failure_uses_fallback_rule() -> None:
    report = triage([make_run(message="Something odd happened")], as_of=NOW)
    assert report.findings[0].rule_id == "GEN-000"


def test_client_policy_changes_rpo_and_tier() -> None:
    run = make_run(message="Connection reset", last_success_at=NOW - timedelta(hours=10))
    lax = triage([run], as_of=NOW).findings[0]
    strict = triage(
        [run],
        Settings(clients={"Demo Client": ClientPolicy(rpo_hours=4, tier=1)}),
        as_of=NOW,
    ).findings[0]
    assert not lax.rpo_breached
    assert strict.rpo_breached
    assert strict.score > lax.score


def test_full_sample_triage(examples_dir, example_settings, as_of) -> None:
    runs = []
    for name in ("veeam_jobs.csv", "cove_devices.csv", "datto_agents.json", "m365_generic.json"):
        runs.extend(load_records(examples_dir / name))
    report = triage(runs, example_settings, as_of=as_of)

    assert report.summary.jobs_evaluated == 20
    assert report.summary.findings == 15
    assert report.summary.healthy_jobs == 5
    by_host = {f.job.host: f for f in report.findings}

    assert report.findings[0].category == "ransomware"
    assert by_host["FAB-FS01"].rule_id == "RANSOM-001"
    assert by_host["TSC-FS02"].rule_id == "RANSOM-002"
    assert by_host["NWD-SQL01"].rule_id == "APP-001"
    assert by_host["NWD-SQL01"].consecutive_failures == 2
    assert by_host["FAB-APP01"].rule_id == "STOR-001"
    assert by_host["FAB-LT02"].rule_id == "RPO-001"
    assert by_host["CTL-SQL02"].rule_id == "VERIFY-001"
    assert by_host["ADA-LT07"].rule_id == "AGENT-001"
    assert "ADA-HV01" not in by_host  # running job inside RPO is healthy
    assert all(f.priority is Priority.P1 for f in report.findings if f.category == "ransomware")
    assert [f.score for f in report.findings] == sorted(
        (f.score for f in report.findings), reverse=True
    )
