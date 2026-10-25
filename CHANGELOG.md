# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-10-25

First public release.

### Added

- Normalised `JobRun` model and pluggable parser registry with auto-detection.
- Parsers for Veeam-style job CSV, Cove-style device CSV, Datto BCDR-style agent JSON and a
  generic normalised JSON/CSV format.
- YAML rules engine with 14 bundled rules covering ransomware indicators (encryption
  extensions, ransom-note text, abnormal change rate), VSS, application-aware processing,
  storage/quota, credentials, verification, network, agent, licensing, locked files, CBT and
  RPO staleness.
- Explainable scoring (severity + RPO breach + failure streak + client tier) mapped to P1-P4.
- Per-client RPO and tier policy via YAML config.
- Optional AI summary layer with `mock`, OpenAI-compatible and Anthropic providers, with
  reversible redaction of client and host names. Off by default.
- Console, JSON and Markdown reports; `--fail-on` exit code for RMM/CI checks.
- Outbound webhook (`--post-to`) and a stdlib HTTP API (`recoverypilot serve`) for n8n.
- Synthetic sample data, 69 pytest tests and GitHub Actions CI (ruff + pytest on 3.11-3.13).

[Unreleased]: https://github.com/ich74851-doom/recoverypilot/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ich74851-doom/recoverypilot/releases/tag/v0.1.0
