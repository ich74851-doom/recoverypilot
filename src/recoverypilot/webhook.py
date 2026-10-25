"""Webhook integration in both directions.

* :func:`post_report` pushes a finished JSON report to a URL (e.g. an n8n Webhook node).
* :func:`serve` runs a small HTTP API so n8n (or anything else) can POST a backup export
  and receive the triage report back synchronously.

The server uses only the standard library and is intended for a trusted network segment
or localhost. Put it behind a reverse proxy with TLS if it must be exposed, and set
``RECOVERYPILOT_TOKEN`` to require a bearer token.
"""

from __future__ import annotations

import hmac
import json
import os
import urllib.error
import urllib.request
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from recoverypilot import __version__
from recoverypilot.config import Settings
from recoverypilot.engine import triage
from recoverypilot.llm import LLMError, enrich_report
from recoverypilot.parsers import ParserError, detect_parser, get_parser
from recoverypilot.parsers.base import parse_datetime
from recoverypilot.report import to_json, to_markdown
from recoverypilot.rules import RuleSet

MAX_BODY_BYTES = 10 * 1024 * 1024


def post_report(url: str, report_json: str, timeout: float = 15.0) -> int:
    """POST a JSON report to ``url`` and return the HTTP status code."""
    request = urllib.request.Request(
        url,
        data=report_json.encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": f"recoverypilot/{__version__}"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return int(response.status)


def handle_triage_request(
    payload: dict[str, Any], settings: Settings, ruleset: RuleSet
) -> dict[str, Any]:
    """Process one ``POST /triage`` body and return the response document.

    Body fields:
        ``content`` (str, required): raw export text (CSV or JSON).
        ``format`` (str): parser name or ``auto`` (default).
        ``as_of`` (str): ISO-8601 evaluation time; defaults to now.
        ``llm`` (bool): run the AI layer with the configured provider.
        ``include_markdown`` (bool): also return a Markdown rendering.
    """
    content = payload.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("'content' must be a non-empty string containing the export")
    fmt = str(payload.get("format") or "auto")
    parser = detect_parser(content) if fmt == "auto" else get_parser(fmt)
    runs = parser.parse(content)
    as_of: datetime | None = parse_datetime(payload.get("as_of")) if payload.get("as_of") else None
    report = triage(runs, settings, ruleset, as_of=as_of, sources=[f"webhook:{parser.name}"])
    if payload.get("llm"):
        report = enrich_report(report, settings.llm)
    body: dict[str, Any] = json.loads(to_json(report))
    if payload.get("include_markdown"):
        body["markdown"] = to_markdown(report)
    return body


def make_handler(settings: Settings, ruleset: RuleSet, token: str | None) -> type:
    """Build a request handler class bound to the given settings and rules."""

    class Handler(BaseHTTPRequestHandler):
        server_version = f"RecoveryPilot/{__version__}"

        def _send(self, status: HTTPStatus, body: dict[str, Any]) -> None:
            data = json.dumps(body, default=str).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _authorised(self) -> bool:
            if not token:
                return True
            supplied = self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
            return hmac.compare_digest(supplied, token)

        def do_GET(self) -> None:
            if self.path.rstrip("/") == "/health":
                self._send(HTTPStatus.OK, {"status": "ok", "version": __version__})
            else:
                self._send(HTTPStatus.NOT_FOUND, {"error": "not found"})

        def do_POST(self) -> None:
            if self.path.rstrip("/") != "/triage":
                self._send(HTTPStatus.NOT_FOUND, {"error": "not found"})
                return
            if not self._authorised():
                self._send(HTTPStatus.UNAUTHORIZED, {"error": "missing or invalid bearer token"})
                return
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0 or length > MAX_BODY_BYTES:
                self._send(HTTPStatus.BAD_REQUEST, {"error": "body missing or too large"})
                return
            try:
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise ValueError("body must be a JSON object")
                self._send(HTTPStatus.OK, handle_triage_request(payload, settings, ruleset))
            except (ValueError, ParserError) as exc:
                self._send(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": str(exc)})
            except LLMError as exc:
                self._send(HTTPStatus.BAD_GATEWAY, {"error": str(exc)})

        def log_message(self, format: str, *args: Any) -> None:
            print(f"[recoverypilot] {self.address_string()} {format % args}", flush=True)

    return Handler


def serve(settings: Settings, ruleset: RuleSet, host: str = "127.0.0.1", port: int = 8080) -> None:
    """Run the webhook API until interrupted."""
    token = os.environ.get("RECOVERYPILOT_TOKEN") or None
    server = ThreadingHTTPServer((host, port), make_handler(settings, ruleset, token))
    auth = "bearer token required" if token else "no auth (set RECOVERYPILOT_TOKEN to enable)"
    print(f"RecoveryPilot webhook listening on http://{host}:{port}  [{auth}]", flush=True)
    print("  GET  /health   POST /triage", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
