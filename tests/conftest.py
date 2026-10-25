"""Shared fixtures."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from recoverypilot.config import Settings, load_settings
from recoverypilot.models import JobRun, JobStatus

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
AS_OF = datetime(2026, 10, 20, 8, 0, tzinfo=UTC)


@pytest.fixture
def examples_dir() -> Path:
    return EXAMPLES


@pytest.fixture
def as_of() -> datetime:
    return AS_OF


@pytest.fixture
def example_settings() -> Settings:
    return load_settings(EXAMPLES / "config.example.yaml")


def make_run(**overrides: object) -> JobRun:
    """Build a JobRun with sensible defaults for unit tests."""
    data: dict[str, object] = {
        "vendor": "test",
        "client": "Demo Client",
        "job_name": "Daily",
        "host": "DEMO-01",
        "status": JobStatus.FAILED,
        "ended_at": datetime(2026, 10, 20, 2, 0, tzinfo=UTC),
        "message": "",
    }
    data.update(overrides)
    return JobRun.model_validate(data)
