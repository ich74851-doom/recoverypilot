"""Veeam-style CSV export (e.g. a job report exported from VBR or Service Provider Console).

Expected columns (case-insensitive)::

    Company, Job Name, Object, Status, Start Time, End Time,
    Transferred (GB), Details, Last Success

``Company`` is optional (falls back to ``unassigned``) because single-tenant VBR exports
do not carry it.
"""

from __future__ import annotations

from recoverypilot.models import JobRun, JobStatus
from recoverypilot.parsers.base import (
    BaseParser,
    csv_header,
    map_status,
    parse_datetime,
    parse_float,
    read_csv,
    register,
)

_STATUS = {
    "success": JobStatus.SUCCESS,
    "warning": JobStatus.WARNING,
    "failed": JobStatus.FAILED,
    "working": JobStatus.RUNNING,
    "running": JobStatus.RUNNING,
    "none": JobStatus.MISSED,
}

_SIGNATURE = {"job name", "status", "start time", "end time", "details"}


def _get(row: dict[str, str], *names: str) -> str:
    lowered = {k.lower(): v for k, v in row.items()}
    for name in names:
        if lowered.get(name):
            return lowered[name]
    return ""


@register
class VeeamParser(BaseParser):
    """Veeam Backup & Replication / VSPC job CSV."""

    name = "veeam"
    description = "Veeam-style job CSV (Job Name, Object, Status, Start/End Time, Details)"

    def sniff(self, text: str, filename: str = "") -> int:
        header = csv_header(text)
        if header >= _SIGNATURE:
            return 90
        return 30 if "veeam" in filename.lower() and "job name" in header else 0

    def parse(self, text: str, filename: str = "") -> list[JobRun]:
        runs: list[JobRun] = []
        for row in read_csv(text):
            runs.append(
                JobRun(
                    vendor="veeam",
                    client=_get(row, "company", "tenant") or "unassigned",
                    job_name=_get(row, "job name"),
                    host=_get(row, "object", "vm name", "host"),
                    status=map_status(_get(row, "status"), _STATUS),
                    started_at=parse_datetime(_get(row, "start time")),
                    ended_at=parse_datetime(_get(row, "end time")),
                    message=_get(row, "details", "reason"),
                    transferred_gb=parse_float(_get(row, "transferred (gb)", "transferred")),
                    change_rate_pct=parse_float(_get(row, "change rate (%)", "change rate")),
                    file_extensions=_get(row, "new extensions"),
                    last_success_at=parse_datetime(_get(row, "last success")),
                )
            )
        return runs
