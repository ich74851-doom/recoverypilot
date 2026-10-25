"""Generic normalised format: JSON or CSV using RecoveryPilot's own field names.

This is the easiest integration point for tools that are not supported natively:
export (or transform in n8n) into these fields and RecoveryPilot can triage it.
"""

from __future__ import annotations

from typing import Any

from recoverypilot.models import JobRun, JobStatus
from recoverypilot.parsers.base import (
    BaseParser,
    ParserError,
    csv_header,
    map_status,
    parse_datetime,
    parse_float,
    parse_int,
    read_csv,
    register,
    try_json,
)

_STATUS = {
    "success": JobStatus.SUCCESS,
    "succeeded": JobStatus.SUCCESS,
    "ok": JobStatus.SUCCESS,
    "warning": JobStatus.WARNING,
    "failed": JobStatus.FAILED,
    "failure": JobStatus.FAILED,
    "error": JobStatus.FAILED,
    "running": JobStatus.RUNNING,
    "missed": JobStatus.MISSED,
}

_REQUIRED = {"client", "job_name", "status"}


def record_from_mapping(row: dict[str, Any], default_vendor: str = "generic") -> JobRun:
    """Build a :class:`JobRun` from a dict that uses normalised field names."""
    missing = [f for f in _REQUIRED if not row.get(f)]
    if missing:
        raise ParserError(f"Record is missing required fields: {', '.join(sorted(missing))}")
    return JobRun(
        vendor=str(row.get("vendor") or default_vendor),
        client=str(row["client"]),
        job_name=str(row["job_name"]),
        host=str(row.get("host") or ""),
        status=map_status(str(row["status"]), _STATUS),
        started_at=parse_datetime(row.get("started_at")),
        ended_at=parse_datetime(row.get("ended_at")),
        message=str(row.get("message") or ""),
        transferred_gb=parse_float(row.get("transferred_gb")),
        change_rate_pct=parse_float(row.get("change_rate_pct")),
        files_changed=parse_int(row.get("files_changed")),
        file_extensions=row.get("file_extensions") or [],
        last_success_at=parse_datetime(row.get("last_success_at")),
    )


@register
class GenericParser(BaseParser):
    """Normalised JSON (list or ``{"jobs": [...]}``) or CSV."""

    name = "generic"
    description = "Normalised JSON/CSV using RecoveryPilot field names (client, job_name, ...)"

    def sniff(self, text: str, filename: str = "") -> int:
        data = try_json(text)
        if data is not None:
            rows = data.get("jobs") if isinstance(data, dict) else data
            if isinstance(rows, list) and rows and isinstance(rows[0], dict):
                return 60 if set(rows[0]) >= _REQUIRED else 0
            return 0
        return 60 if csv_header(text) >= _REQUIRED else 0

    def parse(self, text: str, filename: str = "") -> list[JobRun]:
        data = try_json(text)
        if data is None:
            rows: list[dict[str, Any]] = list(read_csv(text))
        else:
            rows = data.get("jobs", []) if isinstance(data, dict) else data
        if not isinstance(rows, list):
            raise ParserError("Generic JSON must be a list or an object with a 'jobs' list")
        return [record_from_mapping(r) for r in rows]
