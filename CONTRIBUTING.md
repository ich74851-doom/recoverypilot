# Contributing to RecoveryPilot

Thanks for your interest. Bug reports, new rules and new vendor parsers are all welcome.

## Development setup

```bash
git clone https://github.com/ich74851-doom/recoverypilot.git
cd recoverypilot
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
ruff check . && ruff format --check .
```

CI runs the same lint and test steps on Python 3.11, 3.12 and 3.13 for every push and pull
request.

## Adding a classification rule

Most improvements need no Python at all. Add a rule to
`src/recoverypilot/data/default_rules.yaml` (or your own file passed with `--rules`):

1. Give it a unique `id` in the `AREA-NNN` style and a clear `title`.
2. Keep `message_regex` patterns specific; prefer error codes (`0x800423f3`) over vague words.
3. Write remediation steps a first-line technician can follow, in order.
4. Add a parametrised case to `tests/test_rules.py` with an example message.

## Adding a vendor parser

1. Create `src/recoverypilot/parsers/<vendor>.py` with a `BaseParser` subclass decorated
   with `@register`.
2. Implement `sniff()` (return 0-100 confidence) and `parse()` (return `JobRun` objects).
3. Import the module in `parsers/__init__.py`.
4. Add a **synthetic** sample under `examples/` and tests in `tests/test_parsers.py`.

## Data rules (important)

- Never commit real client names, hostnames, IP addresses, logs or exports, even redacted.
  All sample data must be synthetic and marked as such.
- Never commit API keys. LLM keys are read from environment variables only.

## Pull requests

- One logical change per PR, with tests.
- Use clear commit messages (`feat:`, `fix:`, `docs:`, `test:`, `ci:`, `refactor:`).
- Update `CHANGELOG.md` under "Unreleased".
