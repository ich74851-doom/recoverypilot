from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from recoverypilot.cli import main
from recoverypilot.config import Settings
from recoverypilot.rules import RuleSet
from recoverypilot.webhook import handle_triage_request, make_handler

AS_OF = "2026-10-20T08:00:00Z"


def test_cli_triage_writes_reports(examples_dir, tmp_path, capsys) -> None:
    json_out = tmp_path / "out" / "r.json"
    md_out = tmp_path / "out" / "r.md"
    code = main(
        [
            "triage",
            str(examples_dir / "veeam_jobs.csv"),
            str(examples_dir / "cove_devices.csv"),
            "-c",
            str(examples_dir / "config.example.yaml"),
            "--as-of",
            AS_OF,
            "--json-out",
            str(json_out),
            "--md-out",
            str(md_out),
        ]
    )
    assert code == 0
    assert "RANSOM-001" in capsys.readouterr().out
    assert json.loads(json_out.read_text())["summary"]["jobs_evaluated"] == 14
    assert "RANSOM-001" in md_out.read_text()


def test_cli_fail_on_exit_code(examples_dir) -> None:
    args = ["triage", str(examples_dir / "datto_agents.json"), "--as-of", AS_OF]
    assert main([*args, "--fail-on", "P1"]) == 2


def test_cli_json_output_with_mock_llm(examples_dir, capsys) -> None:
    code = main(
        ["triage", str(examples_dir / "m365_generic.json"), "--as-of", AS_OF, "-o", "json", "--llm"]
    )
    assert code == 0
    data = json.loads(capsys.readouterr().out)
    assert data["ai_provider"] == "mock"


def test_cli_rules_and_formats(capsys) -> None:
    assert main(["rules", "list"]) == 0
    assert "VSS-001" in capsys.readouterr().out
    assert main(["formats"]) == 0
    assert "cove" in capsys.readouterr().out
    assert main(["rules", "export"]) == 0
    assert RuleSet.from_text(capsys.readouterr().out).rules


def test_cli_reports_bad_input(tmp_path, capsys) -> None:
    bad = tmp_path / "x.csv"
    bad.write_text("a,b\n1,2\n")
    assert main(["triage", str(bad)]) == 1
    assert "Could not detect" in capsys.readouterr().err


def test_handle_triage_request(examples_dir) -> None:
    body = handle_triage_request(
        {
            "content": (examples_dir / "cove_devices.csv").read_text(),
            "as_of": AS_OF,
            "include_markdown": True,
        },
        Settings(),
        RuleSet.default(),
    )
    assert body["sources"] == ["webhook:cove"]
    assert body["summary"]["jobs_evaluated"] == 6
    assert body["markdown"].startswith("# Backup incident triage report")


def test_handle_triage_request_validates() -> None:
    with pytest.raises(ValueError):
        handle_triage_request({"content": ""}, Settings(), RuleSet.default())


@pytest.fixture
def server():
    httpd = ThreadingHTTPServer(
        ("127.0.0.1", 0), make_handler(Settings(), RuleSet.default(), token="s3cret")
    )
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def _post(url: str, payload: dict, token: str | None) -> tuple[int, dict]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, json.dumps(payload).encode(), headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def test_http_server_end_to_end(server, examples_dir) -> None:
    with urllib.request.urlopen(f"{server}/health", timeout=5) as resp:
        assert json.loads(resp.read())["status"] == "ok"

    payload = {"content": (examples_dir / "datto_agents.json").read_text(), "as_of": AS_OF}
    status, _ = _post(f"{server}/triage", payload, token=None)
    assert status == 401

    status, body = _post(f"{server}/triage", payload, token="s3cret")
    assert status == 200
    assert body["findings"][0]["rule_id"] == "RANSOM-002"

    status, body = _post(f"{server}/triage", {"content": "nonsense"}, token="s3cret")
    assert status == 422
    assert "error" in body
