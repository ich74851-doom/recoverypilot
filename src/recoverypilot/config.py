"""Runtime settings: RPO/SLA policy per client, scoring thresholds and LLM options.

Settings are loaded from an optional YAML file (see ``config.example.yaml``). Every value
has a safe default, so RecoveryPilot runs with no configuration at all.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator


class ClientPolicy(BaseModel):
    """Backup policy for one managed client."""

    rpo_hours: float | None = Field(default=None, gt=0, description="Recovery point objective.")
    tier: int | None = Field(
        default=None, ge=1, le=3, description="1 = business critical, 3 = standard."
    )


class LLMSettings(BaseModel):
    """Optional AI summary layer. Disabled by default; ``mock`` needs no API key."""

    enabled: bool = False
    provider: str = Field(default="mock", description="mock | openai | anthropic")
    model: str = "gpt-4o-mini"
    base_url: str | None = Field(
        default=None, description="Override for OpenAI-compatible gateways (Azure, Ollama, ...)."
    )
    api_key_env: str = Field(
        default="RECOVERYPILOT_LLM_API_KEY", description="Environment variable holding the key."
    )
    timeout_seconds: float = 30.0
    max_findings: int = Field(default=15, ge=1, description="Cap on findings sent to the model.")
    redact: bool = Field(default=True, description="Pseudonymise client and host names.")


class PriorityThresholds(BaseModel):
    """Minimum score for each priority band."""

    p1: int = 80
    p2: int = 60
    p3: int = 40


class Settings(BaseModel):
    """Top-level RecoveryPilot configuration."""

    default_rpo_hours: float = Field(default=24.0, gt=0)
    default_tier: int = Field(default=3, ge=1, le=3)
    clients: dict[str, ClientPolicy] = Field(default_factory=dict)
    priority_thresholds: PriorityThresholds = Field(default_factory=PriorityThresholds)
    rules_file: str | None = None
    webhook_url: str | None = Field(
        default=None, description="If set, the JSON report is POSTed here after each run."
    )
    llm: LLMSettings = Field(default_factory=LLMSettings)

    @field_validator("clients", mode="before")
    @classmethod
    def _normalise_keys(cls, value: object) -> object:
        if isinstance(value, dict):
            return {str(k).strip().lower(): (v or {}) for k, v in value.items()}
        return value

    def policy_for(self, client: str) -> tuple[float, int]:
        """Return ``(rpo_hours, tier)`` for a client, falling back to defaults."""
        policy = self.clients.get(client.strip().lower(), ClientPolicy())
        return (
            policy.rpo_hours or self.default_rpo_hours,
            policy.tier or self.default_tier,
        )


def load_settings(path: str | Path | None = None) -> Settings:
    """Load settings from YAML, or return defaults when ``path`` is ``None``."""
    if path is None:
        return Settings()
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config file {path} must contain a YAML mapping")
    return Settings.model_validate(data)
