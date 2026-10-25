"""Parser base class, registry and shared helpers."""

from __future__ import annotations

import csv
import io
import json
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar

from recoverypilot.models import JobRun, JobStatus


class ParserError(ValueError):
    """Raised when an input cannot be parsed or no parser recognises it."""


class BaseParser(ABC):
    """Base class for vendor export parsers.

    Subclasses set :attr:`name` and implement :meth:`sniff` and :meth:`parse`.
    Inputs are passed as already-decoded text so the same parser works for files on disk
    and for payloads posted to the webhook server.
    """

    name: ClassVar[str] = ""
    description: ClassVar[str] = ""

    @abstractmethod
    def sniff(self, text: str, filename: str = "") -> int:
        """Return a confidence score 0-100 that ``text`` is in this parser's format."""

    @abstractmethod
    def parse(self, text: str, filename: str = "") -> list[JobRun]:
        """Parse ``text`` into normalised job runs."""


_REGISTRY: dict[str, type[BaseParser]] = {}


def register(cls: type[BaseParser]) -> type[BaseParser]:
    """Class decorator that adds a parser to the registry."""
    if not cls.name:
        raise ValueError(f"{cls.__name__} must define a non-empty 'name'")
    _REGISTRY[cls.name] = cls
    return cls


def available_parsers() -> dict[str, str]:
    """Return ``{name: description}`` for every registered parser."""
    return {name: cls.description for name, cls in sorted(_REGISTRY.items())}


def get_parser(name: str) -> BaseParser:
    """Instantiate a parser by registry name."""
    try:
        return _REGISTRY[name]()
    except KeyError as exc:
        known = ", ".join(sorted(_REGISTRY))
        raise ParserError(f"Unknown format '{name}'. Known formats: {known}") from exc


def detect_parser(text: str, filename: str = "") -> BaseParser:
    """Pick the parser with the highest ``sniff`` confidence."""
    best: tuple[int, BaseParser] | None = None
    for cls in _REGISTRY.values():
        parser = cls()
        score = parser.sniff(text, filename)
        if score > 0 and (best is None or score > best[0]):
            best = (score, parser)
    if best is None:
        raise ParserError(f"Could not detect the format of '{filename or 'input'}'")
    return best[1]


def load_records(path: str | Path, fmt: str = "auto") -> list[JobRun]:
    """Read a file from disk and parse it with the named (or detected) parser."""
    p = Path(path)
    text = p.read_text(encoding="utf-8-sig")
    parser = detect_parser(text, p.name) if fmt == "auto" else get_parser(fmt)
    return parser.parse(text, p.name)


# --------------------------------------------------------------------------- helpers

_DATETIME_FORMATS = (
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
)


def parse_datetime(value: Any) -> datetime | None:
    """Parse common export timestamp formats. Naive values are treated as UTC."""
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text or text.lower() in {"never", "n/a", "-", "none", "null"}:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = None
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            for fmt in _DATETIME_FORMATS:
                try:
                    dt = datetime.strptime(text, fmt)
                    break
                except ValueError:
                    continue
        if dt is None:
            raise ParserError(f"Unrecognised timestamp: {value!r}")
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def parse_float(value: Any) -> float | None:
    """Parse a number that may be blank or contain thousands separators."""
    if value is None:
        return None
    text = str(value).strip().replace(",", "").rstrip("%")
    if not text or text in {"-", "n/a"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_int(value: Any) -> int | None:
    """Parse an integer that may be blank."""
    number = parse_float(value)
    return None if number is None else int(number)


def read_csv(text: str) -> list[dict[str, str]]:
    """Read CSV text into dict rows with stripped keys, skipping ``#`` comment lines."""
    lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith("#")]
    reader = csv.DictReader(io.StringIO("\n".join(lines)))
    return [{(k or "").strip(): (v or "").strip() for k, v in row.items()} for row in reader]


def csv_header(text: str) -> set[str]:
    """Return the lower-cased header names of a CSV document (comments skipped)."""
    for line in text.splitlines():
        if line.strip() and not line.lstrip().startswith("#"):
            return {h.strip().strip('"').lower() for h in next(csv.reader([line]))}
    return set()


def try_json(text: str) -> Any | None:
    """Return parsed JSON or ``None`` if the text is not JSON."""
    stripped = text.lstrip()
    if not stripped.startswith(("{", "[")):
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def map_status(value: str, mapping: dict[str, JobStatus]) -> JobStatus:
    """Map a vendor status string (case/space-insensitive) onto :class:`JobStatus`."""
    key = value.strip().lower().replace(" ", "").replace("_", "")
    return mapping.get(key, JobStatus.UNKNOWN)
