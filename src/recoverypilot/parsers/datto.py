"""Datto BCDR style JSON export (per protected agent).

Expected shape::

    {
      "exportType": "datto-bcdr",
      "agents": [
        {
          "organization": "...", "applianceName": "...", "agentName": "...",
          "backupStatus": "success|warning|failed|in progress|missed",
          "lastBackupAttempt": "ISO-8601", "lastSuccessfulBackup": "ISO-8601",
          "errorMessage": "...", "screenshotVerification": "passed|failed|n/a",
          "changeRatePct": 3.1, "newExtensions": [".docx"]
        }
      ]
    }

A failed screenshot verification on an otherwise successful backup is surfaced as a
warning, because an unbootable recovery point is a real DR risk.
"""

from __future__ import annotations

from typing import Any

from recoverypilot.models import JobRun, JobStatus
from recoverypilot.parsers.base import (
    BaseParser,
    ParserError,
    map_status,
    parse_datetime,
    parse_float,
    register,
    try_json,
)

_STATUS = {
    "success": JobStatus.SUCCESS,
    "warning": JobStatus.WARNING,
    "failed": JobStatus.FAILED,
    "failure": JobStatus.FAILED,
    "inprogress": JobStatus.RUNNING,
    "missed": JobStatus.MISSED,
}


@register
class DattoParser(BaseParser):
    """Datto BCDR agent JSON."""

    name = "datto"
    description = 'Datto BCDR-style agent JSON ({"exportType": "datto-bcdr", "agents": [...]})'

    def sniff(self, text: str, filename: str = "") -> int:
        data = try_json(text)
        if isinstance(data, dict):
            if data.get("exportType") == "datto-bcdr":
                return 95
            if isinstance(data.get("agents"), list):
                return 50
        return 0

    def parse(self, text: str, filename: str = "") -> list[JobRun]:
        data = try_json(text)
        if not isinstance(data, dict) or not isinstance(data.get("agents"), list):
            raise ParserError("Datto export must be an object with an 'agents' list")
        return [self._agent(a) for a in data["agents"]]

    @staticmethod
    def _agent(agent: dict[str, Any]) -> JobRun:
        status = map_status(str(agent.get("backupStatus", "")), _STATUS)
        message = str(agent.get("errorMessage") or "")
        if str(agent.get("screenshotVerification", "")).lower() == "failed":
            message = (message + " Screenshot verification failed.").strip()
            if status is JobStatus.SUCCESS:
                status = JobStatus.WARNING
        return JobRun(
            vendor="datto",
            client=str(agent.get("organization") or "unassigned"),
            job_name=f"{agent.get('applianceName', 'appliance')} agent backup",
            host=str(agent.get("agentName") or ""),
            status=status,
            ended_at=parse_datetime(agent.get("lastBackupAttempt")),
            message=message,
            change_rate_pct=parse_float(agent.get("changeRatePct")),
            files_changed=agent.get("filesChanged"),
            file_extensions=agent.get("newExtensions") or [],
            last_success_at=parse_datetime(agent.get("lastSuccessfulBackup")),
        )
