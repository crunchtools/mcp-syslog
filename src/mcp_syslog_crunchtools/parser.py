"""Parsing for the collector's line format.

The collector writes one record per line:

    <rfc3339 timestamp> <host> <source> <program> <SEVERITY> <message>

Embedded newlines are escaped as ``#012`` by rsyslog, so a record never spans
lines and the file can be read a line at a time.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .errors import InvalidTimeRangeError

LINE_RE = re.compile(
    r"^(?P<timestamp>\S+) (?P<host>\S+) (?P<source>\S+) "
    r"(?P<program>\S+) (?P<severity>\S+) (?P<message>.*)$"
)

# The collector emitted five fields (no program) before 2026-08-23. Those lines
# stay in the retention window for 90 days, and parsing them with the six-field
# pattern shifts every column left: the severity slot picks up the first word of
# the message, which then reads as an unknown severity and poisons any counting
# built on it.
LEGACY_LINE_RE = re.compile(
    r"^(?P<timestamp>\S+) (?P<host>\S+) (?P<source>\S+) (?P<severity>\S+) (?P<message>.*)$"
)

# Syslog severities, lowest number is most severe. Filtering by "at least this
# severe" is a <= comparison on these values.
SEVERITY_ORDER: dict[str, int] = {
    "EMERG": 0,
    "ALERT": 1,
    "CRIT": 2,
    "ERR": 3,
    "ERROR": 3,
    "WARNING": 4,
    "WARN": 4,
    "NOTICE": 5,
    "INFO": 6,
    "DEBUG": 7,
}

_RELATIVE_RE = re.compile(r"^(\d+)\s*([smhdw])$", re.IGNORECASE)
_RELATIVE_UNITS = {
    "s": "seconds",
    "m": "minutes",
    "h": "hours",
    "d": "days",
    "w": "weeks",
}


@dataclass(frozen=True)
class LogLine:
    """One parsed record."""

    timestamp: datetime
    host: str
    source: str
    program: str
    severity: str
    message: str
    raw: str

    def format(self, *, show_source: bool = True) -> str:
        """Render for display, dropping fields the caller already knows."""
        stamp = self.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        prefix = f"{stamp} {self.severity}"
        if show_source:
            prefix = f"{stamp} {self.source} {self.severity}"
        # Restore rsyslog's escaped newlines so multi-line output (tracebacks,
        # SELinux alerts) is readable rather than a wall of #012.
        return f"{prefix} {self.message.replace('#012', chr(10) + '    ')}"


def parse_line(raw: str) -> LogLine | None:
    """Parse one record, or return None if it does not match either format.

    Which layout a line uses is decided by where a real severity sits, not by
    guessing at field counts. A six-field line has a known severity in position
    five; if position five is something else but position four is a severity, the
    line predates the program field.

    One case is genuinely ambiguous — ``... mysvc WARNING INFO something`` reads
    as either. It is resolved by noting that the six-field reading would require a
    program literally named ``WARNING``, which does not happen, whereas messages
    beginning with a word like ``INFO`` are everywhere. So when *both* slots look
    like severities, the legacy reading wins.
    """
    stripped = raw.rstrip("\n")

    match = LINE_RE.match(stripped)
    if (
        match is not None
        and is_known_severity(match["severity"])
        and not is_known_severity(match["program"])
    ):
        program = match["program"]
    else:
        legacy = LEGACY_LINE_RE.match(stripped)
        if legacy is None or not is_known_severity(legacy["severity"]):
            # Neither layout fits. Fall back to the six-field reading if it
            # matched at all, so an unrecognised severity is surfaced rather than
            # the whole line being dropped.
            if match is None:
                return None
            program = match["program"]
        else:
            match = legacy
            program = legacy["source"]

    timestamp = _parse_timestamp(match["timestamp"])
    if timestamp is None:
        return None

    return LogLine(
        timestamp=timestamp,
        host=match["host"],
        source=match["source"],
        program=program,
        severity=match["severity"].upper(),
        message=match["message"],
        raw=stripped,
    )


def is_known_severity(value: str) -> bool:
    """Whether ``value`` names a syslog severity."""
    return value.upper() in SEVERITY_ORDER


def _parse_timestamp(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    # Timestamps without an offset would otherwise compare as naive and raise
    # against the timezone-aware bounds every caller supplies.
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def severity_at_least(severity: str, threshold: str) -> bool:
    """True when ``severity`` is at least as severe as ``threshold``."""
    level = SEVERITY_ORDER.get(severity.upper())
    limit = SEVERITY_ORDER.get(threshold.upper())
    if level is None or limit is None:
        return True
    return level <= limit


def parse_time(value: str, *, now: datetime | None = None) -> datetime:
    """Parse an absolute ISO-8601 timestamp or a relative offset like ``30m``.

    Relative values are the common case for an agent triaging an alert — "what
    happened in the last ten minutes" — so they are accepted directly rather than
    making the caller compute a wall-clock time.
    """
    reference = now or datetime.now(timezone.utc)

    relative = _RELATIVE_RE.match(value.strip())
    if relative:
        amount = int(relative.group(1))
        unit = _RELATIVE_UNITS[relative.group(2).lower()]
        return reference - timedelta(**{unit: amount})

    parsed = _parse_timestamp(value.strip())
    if parsed is None:
        raise InvalidTimeRangeError(value)
    return parsed
