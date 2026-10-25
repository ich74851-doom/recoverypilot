from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from recoverypilot.config import LLMSettings
from recoverypilot.engine import triage
from recoverypilot.llm import (
    AnthropicProvider,
    LLMError,
    LLMProvider,
    OpenAICompatibleProvider,
    enrich_report,
    get_provider,
)
from recoverypilot.llm.base import Redactor, parse_reply
from recoverypilot.report import to_console, to_json, to_markdown
from tests.conftest import make_run

NOW = datetime(2026, 10, 20, 8, 0, tzinfo=UTC)


@pytest.fixture
def report():
    runs = [
        make_run(client="Acme Corp", host="ACME-SQL01", message="VSS writer failed"),
        make_run(client="Beta LLC", host="BETA-FS01", message="Disk is full"),
    ]
    return triage(runs, as_of=NOW, sources=["unit"])


def test_json_report_schema(report) -> None:
    data = json.loads(to_json(report))
    assert data["tool"] == "recoverypilot"
    assert data["summary"]["findings"] == 2
    assert {"rule_id", "priority", "score", "remediation", "score_breakdown"} <= set(
        data["findings"][0]
    )


def test_console_and_markdown_render(report) -> None:
    text = to_console(report)
    assert "VSS-001" in text and "STOR-001" in text
    md = to_markdown(report)
    assert md.startswith("# Backup incident triage report")
    assert "**Remediation**" in md


def test_empty_report_renders() -> None:
    empty = triage([], as_of=NOW)
    assert "No incidents" in to_console(empty)
    assert "No incidents" in to_markdown(empty)


def test_mock_enrichment_restores_names(report) -> None:
    enriched = enrich_report(report, LLMSettings(enabled=True))
    assert enriched.ai_provider == "mock"
    assert enriched.ai_summary and "[mock provider]" in enriched.ai_summary
    assert all(f.ai_notes for f in enriched.findings)
    assert report.ai_summary is None  # original untouched


class RecordingProvider(LLMProvider):
    name = "recording"

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def complete(self, system: str, user: str) -> str:
        self.prompts.append(user)
        return '```json\n{"summary": "Fix CLIENT-01 first", "notes": {"F1": "Check HOST-01"}}\n```'


def test_redaction_hides_names_from_provider(report) -> None:
    provider = RecordingProvider()
    enriched = enrich_report(report, LLMSettings(), provider=provider)
    sent = provider.prompts[0]
    assert "Acme Corp" not in sent and "ACME-SQL01" not in sent
    assert "CLIENT-01" in sent
    assert enriched.ai_summary == "Fix Acme Corp first"
    assert enriched.findings[0].ai_notes == "Check ACME-SQL01"


def test_redaction_can_be_disabled(report) -> None:
    provider = RecordingProvider()
    enrich_report(report, LLMSettings(redact=False), provider=provider)
    assert "Acme Corp" in provider.prompts[0]


def test_redactor_prefers_longest_match() -> None:
    r = Redactor([make_run_finding("Acme", "Acme-FS01")])
    assert r.restore(r.redact("Acme-FS01 at Acme")) == "Acme-FS01 at Acme"


def make_run_finding(client: str, host: str):
    return triage([make_run(client=client, host=host, message="x")], as_of=NOW).findings[0]


def test_parse_reply_falls_back_to_text() -> None:
    assert parse_reply("not json").summary == "not json"
    assert parse_reply('{"summary": "ok", "notes": {"F1": "a"}}').notes == {"F1": "a"}


def test_get_provider_selection() -> None:
    assert get_provider(LLMSettings(provider="openai")).name == "openai"
    assert get_provider(LLMSettings(provider="anthropic")).name == "anthropic"
    with pytest.raises(LLMError):
        get_provider(LLMSettings(provider="other"))


def test_http_provider_requires_key(monkeypatch) -> None:
    monkeypatch.delenv("RP_TEST_KEY", raising=False)
    with pytest.raises(LLMError, match="RP_TEST_KEY"):
        OpenAICompatibleProvider("m", "RP_TEST_KEY").complete("s", "u")


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._data = json.dumps(payload).encode()
        self.status = 200

    def read(self) -> bytes:
        return self._data

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


def test_openai_provider_request_shape(monkeypatch) -> None:
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["auth"] = request.get_header("Authorization")
        captured["body"] = json.loads(request.data)
        return FakeResponse({"choices": [{"message": {"content": "hello"}}]})

    monkeypatch.setenv("RP_TEST_KEY", "sk-test")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    provider = OpenAICompatibleProvider("gpt-x", "RP_TEST_KEY", "http://localhost:11434/v1/")
    assert provider.complete("sys", "usr") == "hello"
    assert captured["url"] == "http://localhost:11434/v1/chat/completions"
    assert captured["auth"] == "Bearer sk-test"
    assert captured["body"]["messages"][0] == {"role": "system", "content": "sys"}


def test_anthropic_provider_request_shape(monkeypatch) -> None:
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["key"] = request.get_header("X-api-key")
        captured["body"] = json.loads(request.data)
        return FakeResponse({"content": [{"type": "text", "text": "hi"}]})

    monkeypatch.setenv("RP_TEST_KEY", "ak-test")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    assert AnthropicProvider("claude-x", "RP_TEST_KEY").complete("sys", "usr") == "hi"
    assert captured["url"] == "https://api.anthropic.com/v1/messages"
    assert captured["key"] == "ak-test"
    assert captured["body"]["system"] == "sys"
