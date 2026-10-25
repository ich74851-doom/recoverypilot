"""N-able Cove Data Protection style device/session CSV export.

Expected columns (case-insensitive)::

    Customer, Device name, Data source, Last session status, Last session time,
    Last successful session, Errors, Selected size (GB), Changed files, Change rate (%)

Cove reports statuses such as ``Completed``, ``CompletedWithErrors``, ``Failed``,
``InProgress``, ``NotStarted``, ``Aborted``, ``Interrupted`` and ``OverQuota``.
"""

from __future__ import annotations

from recoverypilot.models import JobRun, JobStatus
from recoverypilot.parsers.base import (
    BaseParser,
    csv_header,
    map_status,
    parse_datetime,
    parse_float,
    parse_int,
    read_csv,
    register,
)

_STATUS = {
    "completed": JobStatus.SUCCESS,
    "completedwitherrors": JobStatus.WARNING,
    "failed": JobStatus.FAILED,
    "aborted": JobStatus.FAILED,
    "interrupted": JobStatus.FAILED,
    "overquota": JobStatus.FAILED,
    "inprogress": JobStatus.RUNNING,
    "notstarted": JobStatus.MISSED,
}

_SIGNATURE = {"device name", "last session status"}


@register
class CoveParser(BaseParser):
    """Cove Data Protection device CSV."""

    name = "cove"
    description = "Cove-style device CSV (Customer, Device name, Last session status, Errors)"

    def sniff(self, text: str, filename: str = "") -> int:
        return 90 if csv_header(text) >= _SIGNATURE else 0

    def parse(self, text: str, filename: str = "") -> list[JobRun]:
        runs: list[JobRun] = []
        for raw in read_csv(text):
            row = {k.lower(): v for k, v in raw.items()}
            status_text = row.get("last session status", "")
            message = row.get("errors", "")
            if status_text.lower() == "overquota" and "quota" not in message.lower():
                message = f"Storage quota exceeded. {message}".strip()
            runs.append(
                JobRun(
                    vendor="cove",
                    client=row.get("customer") or "unassigned",
                    job_name=row.get("data source") or "Files and Folders",
                    host=row.get("device name", ""),
                    status=map_status(status_text, _STATUS),
                    ended_at=parse_datetime(row.get("last session time")),
                    message=message,
                    transferred_gb=parse_float(row.get("selected size (gb)")),
                    files_changed=parse_int(row.get("changed files")),
                    change_rate_pct=parse_float(row.get("change rate (%)")),
                    file_extensions=row.get("new extensions", ""),
                    last_success_at=parse_datetime(row.get("last successful session")),
                )
            )
        return runs
