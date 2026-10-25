"""Triage engine: group runs per job, derive history context, classify and score."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime

from recoverypilot import __version__
from recoverypilot.config import Settings
from recoverypilot.models import (
    Finding,
    JobRun,
    JobStatus,
    Priority,
    Severity,
    TriageReport,
    TriageSummary,
)
from recoverypilot.rules import JobContext, Rule, RuleMatch, RuleSet
from recoverypilot.scoring import priority_for, score_finding

_FAILING = {JobStatus.FAILED, JobStatus.MISSED}
# Runs that leave a usable restore point (a warning usually still does).
_RESTORE_POINT = {JobStatus.SUCCESS, JobStatus.WARNING}
_EPOCH = datetime.min.replace(tzinfo=UTC)

FALLBACK_RULE = Rule(
    id="GEN-000",
    title="Unclassified backup failure",
    category="unclassified",
    severity=Severity.MEDIUM,
    priority=999,
    description="No rule matched this failed or warning job. Consider adding a rule.",
    match=RuleMatch(statuses=[JobStatus.FAILED, JobStatus.WARNING, JobStatus.MISSED]),
    remediation=[
        "Open the job log in the vendor console and capture the exact error text.",
        "Search the vendor knowledge base for the error code.",
        "Add a rule for this error to your rules file so it is classified next time.",
    ],
)


def _ts(run: JobRun) -> datetime:
    return run.timestamp or _EPOCH


def build_context(history: list[JobRun], as_of: datetime, rpo_hours: float) -> JobContext:
    """Derive streak, last-success age and RPO status from one job's run history.

    ``history`` must be sorted oldest to newest.
    """
    streak = 0
    for run in reversed(history):
        if run.status in _FAILING:
            streak += 1
        else:
            break

    candidates = [r.timestamp for r in history if r.status in _RESTORE_POINT and r.timestamp]
    candidates += [r.last_success_at for r in history if r.last_success_at]
    last_success = max(candidates) if candidates else None

    # Without a known last success we cannot prove a breach: one export rarely holds the
    # whole history, so we report the age as unknown rather than guessing.
    hours = None
    breached = False
    if last_success is not None:
        hours = max(0.0, (as_of - last_success).total_seconds() / 3600)
        breached = hours > rpo_hours

    return JobContext(
        consecutive_failures=streak,
        hours_since_success=hours,
        rpo_hours=rpo_hours,
        rpo_breached=breached,
    )


def triage(
    runs: Iterable[JobRun],
    settings: Settings | None = None,
    ruleset: RuleSet | None = None,
    as_of: datetime | None = None,
    sources: list[str] | None = None,
) -> TriageReport:
    """Classify and score the latest run of every job and return a report.

    Args:
        runs: Normalised runs from one or more parsers (any order, any vendor).
        settings: RPO/tier policy and thresholds. Defaults are used when omitted.
        ruleset: Classification rules. The bundled defaults are used when omitted.
        as_of: Point in time used for RPO maths. Defaults to now (UTC).
        sources: Input names recorded in the report.
    """
    settings = settings or Settings()
    ruleset = ruleset or RuleSet.default()
    as_of = as_of or datetime.now(UTC)
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=UTC)

    grouped: dict[tuple[str, str, str], list[JobRun]] = defaultdict(list)
    for run in runs:
        grouped[run.key].append(run)

    findings: list[Finding] = []
    healthy = 0
    for history in grouped.values():
        history.sort(key=_ts)
        latest = history[-1]
        rpo_hours, tier = settings.policy_for(latest.client)
        ctx = build_context(history, as_of, rpo_hours)

        hits = ruleset.evaluate(latest, ctx)
        if not hits:
            fallback_evidence = FALLBACK_RULE.match.evaluate(latest, ctx)
            if fallback_evidence is None:
                healthy += 1
                continue
            primary_rule, evidence, secondary = FALLBACK_RULE, fallback_evidence, []
        else:
            primary_rule, evidence = hits[0].rule, list(hits[0].evidence)
            secondary = [h.rule.id for h in hits[1:]]
            for extra in hits[1:]:
                evidence.extend(e for e in extra.evidence if e not in evidence)

        score, breakdown = score_finding(primary_rule.severity, ctx, tier)
        remediation = list(primary_rule.remediation)
        for extra in hits[1:]:
            remediation.extend(s for s in extra.rule.remediation if s not in remediation)

        findings.append(
            Finding(
                job=latest,
                rule_id=primary_rule.id,
                category=primary_rule.category,
                title=primary_rule.title,
                severity=primary_rule.severity,
                score=score,
                priority=priority_for(score, settings.priority_thresholds),
                score_breakdown=breakdown,
                consecutive_failures=ctx.consecutive_failures,
                hours_since_success=(
                    round(ctx.hours_since_success, 1)
                    if ctx.hours_since_success is not None
                    else None
                ),
                rpo_hours=ctx.rpo_hours,
                rpo_breached=ctx.rpo_breached,
                evidence=evidence,
                remediation=remediation,
                references=list(primary_rule.references),
                secondary_matches=secondary,
            )
        )

    findings.sort(
        key=lambda f: (-f.score, -f.severity.weight, f.job.client, f.job.job_name, f.job.host)
    )
    by_priority = Counter(f.priority.value for f in findings)
    summary = TriageSummary(
        jobs_evaluated=len(grouped),
        healthy_jobs=healthy,
        findings=len(findings),
        by_priority={p.value: by_priority.get(p.value, 0) for p in Priority},
        by_category=dict(sorted(Counter(f.category for f in findings).items())),
        rpo_breaches=sum(1 for f in findings if f.rpo_breached),
    )
    return TriageReport(
        version=__version__,
        generated_at=datetime.now(UTC),
        as_of=as_of,
        sources=sources or [],
        summary=summary,
        findings=findings,
    )
