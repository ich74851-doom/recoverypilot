from __future__ import annotations

import pytest
from pydantic import ValidationError

from recoverypilot.models import JobStatus
from recoverypilot.rules import JobContext, RuleSet
from tests.conftest import make_run

RULES = RuleSet.default()
CTX = JobContext()


def primary(**kwargs: object) -> str | None:
    """Return the id of the strongest rule matching a run built from ``kwargs``."""
    hits = RULES.evaluate(make_run(**kwargs), CTX)
    return hits[0].rule.id if hits else None


def test_default_rules_load_with_unique_ids() -> None:
    ids = [r.id for r in RULES.rules]
    assert len(ids) == len(set(ids))
    assert len(ids) >= 12


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("VSS_E_WRITERERROR_TIMEOUT (0x800423f2) on volume C:", "VSS-001"),
        ("Failed to create shadow copy", "VSS-001"),
        ("SqlServerWriter failed: VSS_E_WRITERERROR_RETRYABLE", "APP-001"),
        ("Not enough free space on target", "STOR-001"),
        ("Storage quota exceeded for device", "STOR-001"),
        ("The RPC server is unavailable. (0x800706BA)", "NET-001"),
        ("Operation timed out after 3600 seconds", "NET-001"),
        ("Logon failure: unknown user name or bad password", "AUTH-001"),
        ("Access is denied. (0x80070005)", "AUTH-001"),
        ("The license has expired", "LICENSE-001"),
        ("file is being used by another process", "LOCK-001"),
        ("CBT data is invalid, failing over to full scan", "CBT-001"),
        ("Found README_TO_DECRYPT.html on share", "RANSOM-002"),
    ],
)
def test_message_classification(message, expected) -> None:
    assert primary(message=message) == expected


def test_status_filter_blocks_success_for_failure_rules() -> None:
    assert primary(status=JobStatus.SUCCESS, message="VSS writer failed") is None


def test_ransomware_extension_flags_even_successful_jobs() -> None:
    hit = RULES.evaluate(make_run(status=JobStatus.SUCCESS, file_extensions=".pdf;.LockBit"), CTX)[
        0
    ]
    assert hit.rule.id == "RANSOM-001"
    assert any(".lockbit" in e for e in hit.evidence)


def test_change_rate_threshold() -> None:
    assert primary(status=JobStatus.SUCCESS, change_rate_pct=39.9) is None
    assert primary(status=JobStatus.SUCCESS, change_rate_pct=40) == "RANSOM-003"


def test_rpo_rule_is_fallback_only() -> None:
    breached = JobContext(rpo_breached=True, hours_since_success=50, rpo_hours=24)
    run = make_run(message="Connection reset by peer")
    hits = RULES.evaluate(run, breached)
    assert hits[0].rule.id == "NET-001"
    assert "RPO-001" in [h.rule.id for h in hits[1:]]
    stale = make_run(status=JobStatus.SUCCESS)
    assert RULES.evaluate(stale, breached)[0].rule.id == "RPO-001"


def test_custom_rules_yaml_with_streak_condition() -> None:
    rules = RuleSet.from_text(
        """
rules:
  - id: X-1
    title: Flapping job
    category: custom
    severity: low
    match:
      min_consecutive_failures: 3
"""
    )
    assert rules.evaluate(make_run(), JobContext(consecutive_failures=2)) == []
    hits = rules.evaluate(make_run(), JobContext(consecutive_failures=3))
    assert hits[0].evidence == ["3 consecutive failed runs"]


def test_rule_without_conditions_is_rejected() -> None:
    with pytest.raises(ValidationError, match="at least one match condition"):
        RuleSet.from_text("rules: [{id: A, title: t, category: c, severity: low, match: {}}]")


def test_invalid_regex_is_rejected() -> None:
    with pytest.raises(ValidationError, match="invalid message_regex"):
        RuleSet.from_text(
            "rules: [{id: A, title: t, category: c, severity: low, "
            "match: {message_regex: ['(unclosed']}}]"
        )


def test_duplicate_ids_rejected() -> None:
    rule = "{id: A, title: t, category: c, severity: low, match: {statuses: [failed]}}"
    with pytest.raises(ValidationError, match="duplicate"):
        RuleSet.from_text(f"rules: [{rule}, {rule}]")
