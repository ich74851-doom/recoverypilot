"""Command-line interface.

Examples::

    recoverypilot triage examples/veeam_jobs.csv examples/cove_devices.csv \\
        --config examples/config.example.yaml --as-of 2026-10-20T08:00:00Z \\
        --json-out reports/triage.json --md-out reports/triage.md
    recoverypilot rules list
    recoverypilot serve --port 8080

Exit codes: 0 = ran successfully (and no finding at/above ``--fail-on``),
1 = usage / input error, 2 = a finding met the ``--fail-on`` priority.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from recoverypilot import __version__
from recoverypilot.config import Settings, load_settings
from recoverypilot.engine import triage
from recoverypilot.llm import LLMError, enrich_report
from recoverypilot.models import JobRun, Priority
from recoverypilot.parsers import ParserError, available_parsers, load_records
from recoverypilot.parsers.base import parse_datetime
from recoverypilot.report import to_console, to_json, to_markdown
from recoverypilot.rules import RuleSet

_PRIORITY_ORDER = [Priority.P1, Priority.P2, Priority.P3, Priority.P4]


def _load_rules(path: str | None, settings: Settings) -> RuleSet:
    chosen = path or settings.rules_file
    return RuleSet.from_yaml(chosen) if chosen else RuleSet.default()


def _write(path: str, text: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def cmd_triage(args: argparse.Namespace) -> int:
    """Run triage over one or more export files."""
    settings = load_settings(args.config)
    if args.llm:
        settings.llm.enabled = True
    if args.llm_provider:
        settings.llm.provider = args.llm_provider
    ruleset = _load_rules(args.rules, settings)

    runs: list[JobRun] = []
    for path in args.inputs:
        runs.extend(load_records(path, args.format))
    as_of = parse_datetime(args.as_of) if args.as_of else None
    report = triage(
        runs, settings, ruleset, as_of=as_of, sources=[Path(p).name for p in args.inputs]
    )

    if settings.llm.enabled:
        report = enrich_report(report, settings.llm)

    if args.output == "json":
        print(to_json(report))
    elif args.output == "markdown":
        print(to_markdown(report))
    else:
        print(to_console(report))

    if args.json_out:
        _write(args.json_out, to_json(report))
    if args.md_out:
        _write(args.md_out, to_markdown(report))

    webhook_url = args.post_to or settings.webhook_url
    if webhook_url:
        from recoverypilot.webhook import post_report

        status = post_report(webhook_url, to_json(report))
        print(f"Report posted to webhook (HTTP {status})", file=sys.stderr)

    if args.fail_on:
        threshold = _PRIORITY_ORDER.index(Priority(args.fail_on))
        if any(_PRIORITY_ORDER.index(f.priority) <= threshold for f in report.findings):
            return 2
    return 0


def cmd_rules(args: argparse.Namespace) -> int:
    """List or export rules."""
    settings = load_settings(args.config)
    if args.action == "export":
        from importlib import resources

        print(
            resources.files("recoverypilot.data")
            .joinpath("default_rules.yaml")
            .read_text(encoding="utf-8"),
            end="",
        )
        return 0
    ruleset = _load_rules(args.rules, settings)
    print(f"{'ID':<12}{'SEVERITY':<10}{'CATEGORY':<14}TITLE")
    for rule in sorted(ruleset.rules, key=lambda r: (-r.severity.weight, r.priority)):
        print(f"{rule.id:<12}{rule.severity.value:<10}{rule.category:<14}{rule.title}")
    return 0


def cmd_formats(_: argparse.Namespace) -> int:
    """List supported input formats."""
    for name, description in available_parsers().items():
        print(f"{name:<9}{description}")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    """Run the webhook API."""
    from recoverypilot.webhook import serve

    settings = load_settings(args.config)
    serve(settings, _load_rules(args.rules, settings), host=args.host, port=args.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser."""
    parser = argparse.ArgumentParser(
        prog="recoverypilot",
        description="AI-assisted backup incident triage for MSP backup operations.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-c", "--config", help="YAML settings file (RPO/tier policy, LLM).")
    common.add_argument("-r", "--rules", help="YAML rules file (defaults to bundled rules).")

    t = sub.add_parser("triage", parents=[common], help="Triage backup job exports.")
    t.add_argument("inputs", nargs="+", help="One or more export files (CSV or JSON).")
    t.add_argument(
        "-f",
        "--format",
        default="auto",
        choices=["auto", *available_parsers()],
        help="Input format (default: auto-detect per file).",
    )
    t.add_argument("--as-of", help="Evaluate RPO at this ISO-8601 time instead of now.")
    t.add_argument(
        "-o",
        "--output",
        default="table",
        choices=["table", "json", "markdown"],
        help="What to print to stdout.",
    )
    t.add_argument("--json-out", help="Also write the JSON report to this path.")
    t.add_argument("--md-out", help="Also write the Markdown report to this path.")
    t.add_argument("--llm", action="store_true", help="Enable the AI summary layer.")
    t.add_argument("--llm-provider", choices=["mock", "openai", "anthropic"])
    t.add_argument("--post-to", help="POST the JSON report to this webhook URL.")
    t.add_argument(
        "--fail-on",
        choices=[p.value for p in Priority],
        help="Exit 2 if any finding is at or above this priority (for RMM/CI checks).",
    )
    t.set_defaults(func=cmd_triage)

    r = sub.add_parser("rules", parents=[common], help="List or export classification rules.")
    r.add_argument("action", choices=["list", "export"], nargs="?", default="list")
    r.set_defaults(func=cmd_rules)

    f = sub.add_parser("formats", help="List supported input formats.")
    f.set_defaults(func=cmd_formats)

    s = sub.add_parser("serve", parents=[common], help="Run the webhook API for n8n.")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8080)
    s.set_defaults(func=cmd_serve)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the ``recoverypilot`` console script."""
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except (ParserError, LLMError, ValueError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
