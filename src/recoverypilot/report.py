"""Render a :class:`~recoverypilot.models.TriageReport` as console text, JSON or Markdown."""

from __future__ import annotations

from recoverypilot.models import Finding, TriageReport


def to_json(report: TriageReport, indent: int = 2) -> str:
    """Serialise the full report as JSON (stable schema for n8n / ticketing)."""
    return report.model_dump_json(indent=indent)


def _where(f: Finding) -> str:
    host = f" / {f.job.host}" if f.job.host else ""
    return f"{f.job.client}{host}"


def _age(f: Finding) -> str:
    if f.hours_since_success is None:
        return "never"
    return f"{f.hours_since_success:g}h"


def to_console(report: TriageReport, max_rows: int = 50) -> str:
    """Plain-text table for terminals and RMM script output (no colour codes)."""
    s = report.summary
    lines = [
        f"RecoveryPilot {report.version} - backup incident triage",
        f"As of {report.as_of:%Y-%m-%d %H:%M} UTC | sources: {', '.join(report.sources) or '-'}",
        (
            f"Jobs evaluated: {s.jobs_evaluated} | healthy: {s.healthy_jobs} | "
            f"findings: {s.findings} | RPO breaches: {s.rpo_breaches}"
        ),
        "Priorities: " + "  ".join(f"{k}={v}" for k, v in s.by_priority.items()),
        "",
    ]
    if not report.findings:
        lines.append("No incidents. All evaluated jobs are healthy and within RPO.")
        return "\n".join(lines)

    header = (
        f"{'PRI':<4}{'SCORE':>5}  {'RULE':<12}{'CATEGORY':<13}{'CLIENT / HOST':<36}{'SINCE OK':>9}"
    )
    lines += [header, "-" * len(header)]
    for f in report.findings[:max_rows]:
        where = _where(f)
        where = where if len(where) <= 34 else where[:31] + "..."
        rpo_flag = "!" if f.rpo_breached else " "
        lines.append(
            f"{f.priority.value:<4}{f.score:>5}  {f.rule_id:<12}{f.category:<13}"
            f"{where:<36}{_age(f):>8}{rpo_flag}"
        )
    if len(report.findings) > max_rows:
        lines.append(f"... {len(report.findings) - max_rows} more in the JSON/Markdown report")
    lines += ["", "! = RPO breached"]

    top = report.findings[0]
    lines += [
        "",
        f"Top incident: [{top.priority.value}] {top.title}",
        f"  {_where(top)} ({top.job.vendor}, {top.job.job_name})",
        f"  Evidence: {'; '.join(top.evidence) or '-'}",
        f"  First step: {top.remediation[0] if top.remediation else '-'}",
    ]
    if report.ai_summary:
        lines += ["", f"AI summary ({report.ai_provider}):", f"  {report.ai_summary}"]
    return "\n".join(lines)


def _md_escape(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def to_markdown(report: TriageReport) -> str:
    """Markdown report suitable for a ticket note, Teams/Slack post or a wiki page."""
    s = report.summary
    out = [
        "# Backup incident triage report",
        "",
        f"- **Generated:** {report.generated_at:%Y-%m-%d %H:%M} UTC by RecoveryPilot "
        f"{report.version}",
        f"- **Evaluated as of:** {report.as_of:%Y-%m-%d %H:%M} UTC",
        f"- **Sources:** {', '.join(report.sources) or '-'}",
        f"- **Jobs evaluated:** {s.jobs_evaluated} (healthy: {s.healthy_jobs})",
        f"- **Findings:** {s.findings} | **RPO breaches:** {s.rpo_breaches}",
        "",
        "| Priority | Count |",
        "| --- | --- |",
        *[f"| {k} | {v} |" for k, v in s.by_priority.items()],
        "",
    ]
    if report.ai_summary:
        out += [f"## AI summary ({report.ai_provider})", "", report.ai_summary, ""]
    if not report.findings:
        out.append("No incidents. All evaluated jobs are healthy and within RPO.")
        return "\n".join(out) + "\n"

    out += [
        "## Findings",
        "",
        "| Priority | Score | Rule | Client | Host | Vendor | Since last success | RPO |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for f in report.findings:
        out.append(
            f"| {f.priority.value} | {f.score} | {f.rule_id} | {_md_escape(f.job.client)} | "
            f"{_md_escape(f.job.host or '-')} | {f.job.vendor} | {_age(f)} | "
            f"{'breached' if f.rpo_breached else 'ok'} ({f.rpo_hours:g}h) |"
        )
    out.append("")
    for f in report.findings:
        out += [
            f"### [{f.priority.value}] {f.title}: {_md_escape(_where(f))}",
            "",
            f"- **Rule:** `{f.rule_id}` ({f.category}, base severity {f.severity.value})",
            f"- **Job:** {f.job.vendor} / {_md_escape(f.job.job_name)} "
            f"/ status `{f.job.status.value}`",
            f"- **Message:** {_md_escape(f.job.message) or '-'}",
            f"- **Evidence:** {'; '.join(f.evidence) or '-'}",
            "- **Score:** "
            + " + ".join(f"{c.factor} {c.points}" for c in f.score_breakdown)
            + f" = **{f.score}**",
        ]
        if f.secondary_matches:
            out.append(f"- **Also matched:** {', '.join(f.secondary_matches)}")
        if f.ai_notes:
            out.append(f"- **AI note:** {_md_escape(f.ai_notes)}")
        out += ["", "**Remediation**", ""]
        out += [f"{i}. {step}" for i, step in enumerate(f.remediation, 1)]
        if f.references:
            out += ["", "References: " + ", ".join(f.references)]
        out.append("")
    return "\n".join(out)
