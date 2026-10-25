"""Core data models shared by parsers, the rules engine, scoring and reporting.

All vendor formats are normalised into :class:`JobRun` so that everything downstream
is vendor-agnostic.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class JobStatus(StrEnum):
    """Normalised outcome of a single backup job run."""

    SUCCESS = "success"
    WARNING = "warning"
    FAILED = "failed"
    RUNNING = "running"
    MISSED = "missed"
    UNKNOWN = "unknown"


class Severity(StrEnum):
    """Base severity assigned by a rule, before contextual scoring."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def weight(self) -> int:
        """Numeric base used by the scoring model (0-80)."""
        return {"info": 0, "low": 15, "medium": 35, "high": 55, "critical": 80}[self.value]


class Priority(StrEnum):
    """Ticket-style priority derived from the final score."""

    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class JobRun(BaseModel):
    """One backup job run, normalised from any supported vendor export."""

    model_config = ConfigDict(extra="ignore")

    vendor: str = Field(description="Source product, e.g. 'veeam', 'cove', 'datto'.")
    client: str = Field(description="Managed client / tenant the job belongs to.")
    job_name: str
    host: str = Field(default="", description="Protected machine or object name.")
    status: JobStatus
    started_at: datetime | None = None
    ended_at: datetime | None = None
    message: str = Field(default="", description="Vendor error / warning text.")
    transferred_gb: float | None = None
    change_rate_pct: float | None = Field(
        default=None, description="Percent of protected data changed since the last run."
    )
    files_changed: int | None = None
    file_extensions: list[str] = Field(
        default_factory=list, description="Sample of new file extensions observed in the run."
    )
    last_success_at: datetime | None = Field(
        default=None, description="Last successful run, if the export provides it."
    )

    @field_validator("file_extensions", mode="before")
    @classmethod
    def _split_extensions(cls, value: object) -> object:
        """Accept a ``;``/``,`` separated string as well as a list."""
        if value is None or value == "":
            return []
        if isinstance(value, str):
            parts = value.replace(",", ";").split(";")
            return [p.strip().lower() for p in parts if p.strip()]
        return value

    @property
    def key(self) -> tuple[str, str, str]:
        """Identity of the job across runs: (client, job_name, host)."""
        return (self.client, self.job_name, self.host)

    @property
    def timestamp(self) -> datetime | None:
        """Best available point in time for ordering runs."""
        return self.ended_at or self.started_at


class ScoreComponent(BaseModel):
    """One explainable contribution to a finding's score."""

    factor: str
    points: int
    detail: str


class Finding(BaseModel):
    """A triaged incident for one backup job."""

    job: JobRun
    rule_id: str
    category: str
    title: str
    severity: Severity
    score: int = Field(ge=0, le=100)
    priority: Priority
    score_breakdown: list[ScoreComponent] = Field(default_factory=list)
    consecutive_failures: int = 0
    hours_since_success: float | None = None
    rpo_hours: float
    rpo_breached: bool = False
    evidence: list[str] = Field(default_factory=list)
    remediation: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)
    secondary_matches: list[str] = Field(default_factory=list)
    ai_notes: str | None = None


class TriageSummary(BaseModel):
    """Aggregate counts for a triage run."""

    jobs_evaluated: int
    healthy_jobs: int
    findings: int
    by_priority: dict[str, int]
    by_category: dict[str, int]
    rpo_breaches: int


class TriageReport(BaseModel):
    """Complete output of one triage run."""

    tool: str = "recoverypilot"
    version: str
    generated_at: datetime
    as_of: datetime
    sources: list[str]
    summary: TriageSummary
    findings: list[Finding]
    ai_summary: str | None = None
    ai_provider: str | None = None
