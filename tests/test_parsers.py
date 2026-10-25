from __future__ import annotations

import json

import pytest

from recoverypilot.models import JobStatus
from recoverypilot.parsers import (
    ParserError,
    available_parsers,
    detect_parser,
    get_parser,
    load_records,
)
from recoverypilot.parsers.base import parse_datetime


def test_all_builtin_parsers_registered() -> None:
    assert set(available_parsers()) >= {"generic", "veeam", "cove", "datto"}


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("veeam_jobs.csv", "veeam"),
        ("cove_devices.csv", "cove"),
        ("datto_agents.json", "datto"),
        ("m365_generic.json", "generic"),
    ],
)
def test_detects_each_sample(examples_dir, filename, expected) -> None:
    text = (examples_dir / filename).read_text(encoding="utf-8")
    assert detect_parser(text, filename).name == expected


def test_veeam_parsing(examples_dir) -> None:
    runs = load_records(examples_dir / "veeam_jobs.csv")
    assert len(runs) == 13
    sql = [r for r in runs if r.host == "NWD-SQL01"]
    assert [r.status for r in sql] == [JobStatus.SUCCESS, JobStatus.FAILED, JobStatus.FAILED]
    assert "0x800423f3" in sql[-1].message
    fs = next(r for r in runs if r.host == "FAB-FS01" and r.change_rate_pct == 63.0)
    assert fs.file_extensions == [".docx", ".akira"]
    running = next(r for r in runs if r.host == "ADA-HV01")
    assert running.status is JobStatus.RUNNING
    assert running.ended_at is None
    assert running.last_success_at is not None


def test_cove_status_mapping_and_quota_message(examples_dir) -> None:
    runs = {r.host: r for r in load_records(examples_dir / "cove_devices.csv")}
    assert runs["TSC-RECEPTION01"].status is JobStatus.SUCCESS
    assert runs["NWD-WS03"].status is JobStatus.WARNING
    assert runs["ADA-LT07"].status is JobStatus.MISSED
    assert runs["ADA-FS01"].status is JobStatus.FAILED
    assert "quota" in runs["ADA-FS01"].message.lower()


def test_datto_screenshot_failure_downgrades_success(examples_dir) -> None:
    runs = {r.host: r for r in load_records(examples_dir / "datto_agents.json")}
    assert runs["CTL-SQL02"].status is JobStatus.WARNING
    assert "Screenshot verification failed" in runs["CTL-SQL02"].message
    assert runs["TSC-DC01"].status is JobStatus.SUCCESS


def test_generic_csv_roundtrip() -> None:
    text = "client,job_name,status,ended_at,message\nAcme,Nightly,error,2026-10-20T01:00:00Z,boom\n"
    runs = get_parser("generic").parse(text)
    assert runs[0].status is JobStatus.FAILED
    assert runs[0].ended_at is not None and runs[0].ended_at.tzinfo is not None


def test_generic_missing_fields_raise() -> None:
    with pytest.raises(ParserError, match="job_name"):
        get_parser("generic").parse(json.dumps([{"client": "Acme", "status": "failed"}]))


def test_unknown_format_raises() -> None:
    with pytest.raises(ParserError):
        detect_parser("hello,world\n1,2\n", "mystery.csv")
    with pytest.raises(ParserError, match="Known formats"):
        get_parser("nope")


@pytest.mark.parametrize(
    "value",
    ["2026-10-20T01:00:00Z", "2026-10-20 01:00:00", "2026-10-20 01:00", "20/10/2026 01:00"],
)
def test_parse_datetime_formats(value) -> None:
    dt = parse_datetime(value)
    assert dt is not None
    assert (dt.year, dt.month, dt.day, dt.hour) == (2026, 10, 20, 1)
    assert dt.tzinfo is not None


def test_parse_datetime_blank_and_never() -> None:
    assert parse_datetime("") is None
    assert parse_datetime("Never") is None
    with pytest.raises(ParserError):
        parse_datetime("yesterday-ish")
