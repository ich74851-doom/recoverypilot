"""Pluggable vendor parsers.

Every parser converts one export format into a list of :class:`~recoverypilot.models.JobRun`.
Parsers register themselves with :func:`register` and are selected either explicitly by
name or automatically via :func:`detect_parser`.

To add a vendor, subclass :class:`BaseParser`, implement ``sniff`` and ``parse``, and
decorate it with ``@register``. See ``docs/architecture.md``.
"""

# Import built-in parsers so they self-register.
from recoverypilot.parsers import cove, datto, generic, veeam  # noqa: F401
from recoverypilot.parsers.base import (
    BaseParser,
    ParserError,
    available_parsers,
    detect_parser,
    get_parser,
    load_records,
    register,
)

__all__ = [
    "BaseParser",
    "ParserError",
    "available_parsers",
    "detect_parser",
    "get_parser",
    "load_records",
    "register",
]
