# Security policy

## Supported versions

| Version | Supported |
| --- | --- |
| 0.1.x | Yes |

## Reporting a vulnerability

Please **do not open a public issue** for security problems. Use GitHub's private
vulnerability reporting instead: open the **Security** tab of this repository and choose
**Report a vulnerability**. Include steps to reproduce and the impact you expect. You should
get an acknowledgement within a few days.

## Design notes for operators

RecoveryPilot handles backup metadata that can reveal client names, hostnames and
infrastructure details. It is built to keep that data under your control:

- **The AI layer is off by default.** Nothing leaves the machine unless you enable `--llm`
  (or `llm.enabled: true`) with a non-mock provider.
- **Redaction is on by default.** Client and host names are replaced with tokens such as
  `CLIENT-01` / `HOST-01` before a prompt is sent and restored locally in the output. Free
  text in error messages is sent as-is (truncated), so review your data before enabling an
  external provider. A self-hosted OpenAI-compatible endpoint (e.g. Ollama) is supported via
  `llm.base_url`.
- **API keys are only read from environment variables** (`llm.api_key_env`), never from the
  config file.
- **The webhook server binds to 127.0.0.1 by default**, has no TLS, and should run behind a
  reverse proxy if exposed. Set `RECOVERYPILOT_TOKEN` to require a bearer token (compared in
  constant time). Request bodies are capped at 10 MB.
- **YAML is loaded with `yaml.safe_load`** only.
- Ransomware indicators in RecoveryPilot are heuristics to speed up escalation. They are not
  a replacement for EDR or a security investigation.
