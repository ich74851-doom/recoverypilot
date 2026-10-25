"""Optional AI layer: summarise triaged findings with an LLM (off by default).

Use :func:`enrich_report` to add ``ai_summary`` and per-finding ``ai_notes`` to a report.
Providers: ``mock`` (offline, deterministic), ``openai`` (any OpenAI-compatible endpoint)
and ``anthropic``.
"""

from __future__ import annotations

from recoverypilot.config import LLMSettings
from recoverypilot.llm.base import (
    SYSTEM_PROMPT,
    AIResult,
    LLMError,
    LLMProvider,
    Redactor,
    build_user_prompt,
    finding_ref,
    parse_reply,
)
from recoverypilot.llm.http import AnthropicProvider, OpenAICompatibleProvider
from recoverypilot.llm.mock import MockProvider
from recoverypilot.models import TriageReport

__all__ = [
    "AIResult",
    "AnthropicProvider",
    "LLMError",
    "LLMProvider",
    "MockProvider",
    "OpenAICompatibleProvider",
    "enrich_report",
    "get_provider",
]


def get_provider(settings: LLMSettings) -> LLMProvider:
    """Instantiate the configured provider."""
    name = settings.provider.lower()
    if name == "mock":
        return MockProvider()
    if name in {"openai", "openai-compatible"}:
        return OpenAICompatibleProvider(
            settings.model, settings.api_key_env, settings.base_url, settings.timeout_seconds
        )
    if name == "anthropic":
        return AnthropicProvider(
            settings.model, settings.api_key_env, settings.base_url, settings.timeout_seconds
        )
    raise LLMError(f"Unknown LLM provider '{settings.provider}' (use mock, openai or anthropic)")


def enrich_report(
    report: TriageReport, settings: LLMSettings, provider: LLMProvider | None = None
) -> TriageReport:
    """Return a copy of ``report`` with AI summary and notes added.

    Only the top ``settings.max_findings`` findings are sent. Names are pseudonymised when
    ``settings.redact`` is true and restored in the returned text.
    """
    provider = provider or get_provider(settings)
    enriched = report.model_copy(deep=True)
    selected = enriched.findings[: settings.max_findings]
    redactor = Redactor(selected) if settings.redact else None

    raw = provider.complete(SYSTEM_PROMPT, build_user_prompt(selected, redactor))
    result = parse_reply(raw)
    restore = redactor.restore if redactor else (lambda s: s)

    enriched.ai_summary = restore(result.summary) or None
    enriched.ai_provider = provider.name
    for i, finding in enumerate(selected):
        note = result.notes.get(finding_ref(i))
        if note:
            finding.ai_notes = restore(note)
    return enriched
