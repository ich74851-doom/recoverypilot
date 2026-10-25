"""Provider interface, prompt construction and redaction for the optional AI layer.

The AI layer never decides severity or priority: those come from the deterministic rules
engine. The model only writes a shift-handover summary and per-finding notes, working from
the engine's findings. Client and host names are pseudonymised before anything is sent and
restored locally afterwards.
"""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from recoverypilot.models import Finding

SYSTEM_PROMPT = (
    "You are a senior backup and disaster recovery engineer at a managed service provider. "
    "You receive backup incidents that a deterministic rules engine has already classified "
    "and prioritised. Do not change priorities or invent facts that are not in the data. "
    "Write for a technician starting a shift: concise, specific, action-oriented. "
    'Reply with JSON only: {"summary": "<markdown, max 120 words>", '
    '"notes": {"<finding id>": "<one or two sentences of next-step advice>"}}'
)


class LLMError(RuntimeError):
    """Raised when a provider call fails or is misconfigured."""


@dataclass
class AIResult:
    """Parsed model output."""

    summary: str
    notes: dict[str, str] = field(default_factory=dict)


class LLMProvider(ABC):
    """Minimal chat-completion interface implemented by every provider."""

    name: str = "base"

    @abstractmethod
    def complete(self, system: str, user: str) -> str:
        """Send one system + user message pair and return the raw text reply."""


class Redactor:
    """Reversible pseudonymisation of client and host names."""

    def __init__(self, findings: list[Finding]) -> None:
        self._forward: dict[str, str] = {}
        clients = sorted({f.job.client for f in findings if f.job.client})
        hosts = sorted({f.job.host for f in findings if f.job.host} - set(clients))
        for i, name in enumerate(clients, 1):
            self._forward[name] = f"CLIENT-{i:02d}"
        for i, name in enumerate(hosts, 1):
            self._forward[name] = f"HOST-{i:02d}"
        self._reverse = {v: k for k, v in self._forward.items()}

    def _sub(self, text: str, mapping: dict[str, str]) -> str:
        if not mapping or not text:
            return text
        keys = sorted(mapping, key=len, reverse=True)
        pattern = re.compile("|".join(re.escape(k) for k in keys))
        return pattern.sub(lambda m: mapping[m.group(0)], text)

    def redact(self, text: str) -> str:
        """Replace real names with tokens."""
        return self._sub(text, self._forward)

    def restore(self, text: str) -> str:
        """Replace tokens with the original names."""
        return self._sub(text, self._reverse)


def finding_ref(index: int) -> str:
    """Stable short id used to key per-finding notes (F1, F2, ...)."""
    return f"F{index + 1}"


def build_user_prompt(findings: list[Finding], redactor: Redactor | None) -> str:
    """Serialise findings into a compact JSON prompt, optionally redacted."""
    items = []
    for i, f in enumerate(findings):
        items.append(
            {
                "id": finding_ref(i),
                "priority": f.priority.value,
                "score": f.score,
                "rule": f.rule_id,
                "category": f.category,
                "title": f.title,
                "client": f.job.client,
                "host": f.job.host,
                "vendor": f.job.vendor,
                "status": f.job.status.value,
                "message": f.job.message[:400],
                "consecutive_failures": f.consecutive_failures,
                "hours_since_success": f.hours_since_success,
                "rpo_hours": f.rpo_hours,
                "evidence": f.evidence,
            }
        )
    text = json.dumps({"incidents": items}, indent=1)
    return redactor.redact(text) if redactor else text


def parse_reply(raw: str) -> AIResult:
    """Parse the model's JSON reply, tolerating code fences or plain text."""
    cleaned = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return AIResult(summary=raw.strip())
    if not isinstance(data, dict):
        return AIResult(summary=raw.strip())
    notes = data.get("notes") or {}
    return AIResult(
        summary=str(data.get("summary", "")).strip(),
        notes={str(k): str(v) for k, v in notes.items()} if isinstance(notes, dict) else {},
    )
