"""Deterministic, YAML-driven rules engine for classifying backup job outcomes.

A rule matches when **all** of the conditions it specifies hold. Within a list condition
(``statuses``, ``message_regex``, ``extensions_any``) **any** item may match. Rules carry
their own severity, remediation steps and references, so operational knowledge lives in
version-controlled YAML rather than in code.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, PrivateAttr, field_validator, model_validator

from recoverypilot.models import JobRun, JobStatus, Severity


@dataclass(frozen=True)
class JobContext:
    """History-derived facts about a job, computed by the triage engine."""

    consecutive_failures: int = 0
    hours_since_success: float | None = None
    rpo_hours: float = 24.0
    rpo_breached: bool = False


class RuleMatch(BaseModel):
    """Conditions for a rule. Omitted conditions are ignored."""

    statuses: list[JobStatus] | None = None
    vendors: list[str] | None = None
    message_regex: list[str] | None = None
    extensions_any: list[str] | None = None
    min_change_rate_pct: float | None = None
    min_files_changed: int | None = None
    min_consecutive_failures: int | None = None
    rpo_breached: bool | None = None

    _patterns: list[re.Pattern[str]] = PrivateAttr(default_factory=list)

    @field_validator("extensions_any", mode="after")
    @classmethod
    def _normalise_ext(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return [v.lower() if v.startswith(".") else f".{v.lower()}" for v in value]

    @model_validator(mode="after")
    def _compile(self) -> RuleMatch:
        if not self.model_dump(exclude_none=True):
            raise ValueError("a rule must define at least one match condition")
        try:
            self._patterns = [re.compile(p, re.IGNORECASE) for p in self.message_regex or []]
        except re.error as exc:
            raise ValueError(f"invalid message_regex: {exc}") from exc
        return self

    def evaluate(self, job: JobRun, ctx: JobContext) -> list[str] | None:
        """Return evidence strings if every condition matches, else ``None``."""
        evidence: list[str] = []
        if self.statuses is not None:
            if job.status not in self.statuses:
                return None
            evidence.append(f"status={job.status.value}")
        if self.vendors is not None and job.vendor.lower() not in {v.lower() for v in self.vendors}:
            return None
        if self._patterns:
            hit = next((p for p in self._patterns if p.search(job.message)), None)
            if hit is None:
                return None
            evidence.append(f"message matches /{hit.pattern}/")
        if self.extensions_any is not None:
            found = sorted(set(job.file_extensions) & set(self.extensions_any))
            if not found:
                return None
            evidence.append(f"suspicious extensions observed: {', '.join(found)}")
        if self.min_change_rate_pct is not None:
            if job.change_rate_pct is None or job.change_rate_pct < self.min_change_rate_pct:
                return None
            evidence.append(
                f"change rate {job.change_rate_pct:g}% >= {self.min_change_rate_pct:g}%"
            )
        if self.min_files_changed is not None:
            if job.files_changed is None or job.files_changed < self.min_files_changed:
                return None
            evidence.append(f"{job.files_changed} files changed")
        if self.min_consecutive_failures is not None:
            if ctx.consecutive_failures < self.min_consecutive_failures:
                return None
            evidence.append(f"{ctx.consecutive_failures} consecutive failed runs")
        if self.rpo_breached is not None:
            if ctx.rpo_breached != self.rpo_breached:
                return None
            if ctx.rpo_breached:
                age = (
                    f"{ctx.hours_since_success:.1f}h since last success"
                    if ctx.hours_since_success is not None
                    else "no successful run on record"
                )
                evidence.append(f"RPO {ctx.rpo_hours:g}h breached ({age})")
        return evidence


class Rule(BaseModel):
    """One classification rule."""

    id: str
    title: str
    category: str
    severity: Severity
    priority: int = Field(default=100, description="Tie-breaker: lower wins.")
    fallback: bool = Field(
        default=False,
        description="Only the primary classification when no non-fallback rule matched.",
    )
    description: str = ""
    match: RuleMatch
    remediation: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)


@dataclass
class RuleHit:
    """A rule that matched a job, with the evidence that triggered it."""

    rule: Rule
    evidence: list[str] = field(default_factory=list)


class RuleSet(BaseModel):
    """An ordered collection of rules loaded from YAML."""

    version: int = 1
    rules: list[Rule]

    @model_validator(mode="after")
    def _unique_ids(self) -> RuleSet:
        ids = [r.id for r in self.rules]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            raise ValueError(f"duplicate rule ids: {', '.join(dupes)}")
        return self

    @classmethod
    def from_yaml(cls, path: str | Path) -> RuleSet:
        """Load a rules file from disk."""
        return cls.from_text(Path(path).read_text(encoding="utf-8"))

    @classmethod
    def from_text(cls, text: str) -> RuleSet:
        """Load rules from YAML text."""
        return cls.model_validate(yaml.safe_load(text))

    @classmethod
    def default(cls) -> RuleSet:
        """Load the rules bundled with the package."""
        text = (
            resources.files("recoverypilot.data")
            .joinpath("default_rules.yaml")
            .read_text(encoding="utf-8")
        )
        return cls.from_text(text)

    def evaluate(self, job: JobRun, ctx: JobContext) -> list[RuleHit]:
        """Return all matching rules, strongest first.

        Ordering: specific rules before ``fallback`` rules, then severity (desc), then
        priority (asc).
        """
        hits = [
            RuleHit(rule, evidence)
            for rule in self.rules
            if (evidence := rule.match.evaluate(job, ctx)) is not None
        ]
        hits.sort(
            key=lambda h: (h.rule.fallback, -h.rule.severity.weight, h.rule.priority, h.rule.id)
        )
        return hits
