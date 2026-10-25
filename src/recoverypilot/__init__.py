"""RecoveryPilot: AI-assisted backup incident triage for MSP backup operations.

The package turns raw backup job exports into prioritised, explainable incidents:

1. :mod:`recoverypilot.parsers` normalise vendor exports into :class:`~recoverypilot.models.JobRun`.
2. :mod:`recoverypilot.rules` classifies each job with a deterministic YAML rules file.
3. :mod:`recoverypilot.scoring` scores severity against RPO, failure streaks and client tier.
4. :mod:`recoverypilot.llm` optionally adds an AI-written summary (off by default).
5. :mod:`recoverypilot.report` renders console, JSON and Markdown output.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
