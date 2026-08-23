"""Parsing tests."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from mcp_syslog_crunchtools.errors import InvalidTimeRangeError
from mcp_syslog_crunchtools.parser import parse_line, parse_time, severity_at_least


def test_parses_journal_format_line() -> None:
    raw = (
        "2026-08-23T15:16:44.380222+00:00 lotor.dc3.crunchtools.com "
        "mcp-memory mcp-memory INFO HTTP Request: POST https://example.com"
    )
    parsed = parse_line(raw)
    assert parsed is not None
    assert parsed.source == "mcp-memory"
    assert parsed.program == "mcp-memory"
    assert parsed.severity == "INFO"
    assert parsed.message == "HTTP Request: POST https://example.com"


def test_parses_forwarded_line_where_source_and_program_differ() -> None:
    """The systemd-container case: filed under the service, program preserved."""
    raw = (
        "2026-08-23T15:41:52+00:00 crunchtools.com crunchtools.com "
        "httpd ERR AH00169: caught SIGTERM"
    )
    parsed = parse_line(raw)
    assert parsed is not None
    assert parsed.source == "crunchtools.com"
    assert parsed.program == "httpd"
    assert parsed.message == "AH00169: caught SIGTERM"


def test_message_containing_spaces_is_not_split() -> None:
    raw = "2026-08-23T10:00:00+00:00 host src prog INFO a b c d e f"
    parsed = parse_line(raw)
    assert parsed is not None
    assert parsed.message == "a b c d e f"


def test_malformed_line_returns_none() -> None:
    assert parse_line("this is not a log line") is None
    assert parse_line("") is None


def test_unparseable_timestamp_returns_none() -> None:
    assert parse_line("not-a-time host src prog INFO message") is None


def test_escaped_newlines_are_restored_for_display() -> None:
    """rsyslog escapes embedded newlines; a traceback should not print as #012."""
    raw = "2026-08-23T10:00:00+00:00 host src prog ERR line one#012line two"
    parsed = parse_line(raw)
    assert parsed is not None
    assert "#012" not in parsed.format()
    assert "line two" in parsed.format()


@pytest.mark.parametrize(
    ("severity", "threshold", "expected"),
    [
        ("ERR", "ERR", True),
        ("CRIT", "ERR", True),
        ("EMERG", "WARNING", True),
        ("INFO", "ERR", False),
        ("DEBUG", "INFO", False),
        ("WARNING", "WARNING", True),
        ("INFO", "INFO", True),
    ],
)
def test_severity_threshold_is_at_least_semantics(
    severity: str, threshold: str, expected: bool
) -> None:
    assert severity_at_least(severity, threshold) is expected


def test_unknown_severity_is_kept_rather_than_dropped() -> None:
    """Better to show an unrecognised severity than silently hide the line."""
    assert severity_at_least("WEIRD", "ERR") is True


def test_relative_time_offsets() -> None:
    now = datetime(2026, 8, 23, 12, 0, 0, tzinfo=timezone.utc)
    assert parse_time("30m", now=now) == datetime(2026, 8, 23, 11, 30, tzinfo=timezone.utc)
    assert parse_time("2h", now=now) == datetime(2026, 8, 23, 10, 0, tzinfo=timezone.utc)
    assert parse_time("3d", now=now) == datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)


def test_absolute_time_is_parsed() -> None:
    assert parse_time("2026-08-23T10:00:00+00:00") == datetime(
        2026, 8, 23, 10, 0, tzinfo=timezone.utc
    )


def test_naive_timestamp_is_treated_as_utc() -> None:
    """Naive datetimes would raise when compared against the aware query bounds."""
    parsed = parse_time("2026-08-23T10:00:00")
    assert parsed.tzinfo is not None


def test_bad_time_raises() -> None:
    with pytest.raises(InvalidTimeRangeError):
        parse_time("last tuesday")


def test_parses_legacy_five_field_line() -> None:
    """The collector emitted five fields before 2026-08-23; those stay in retention.

    Parsed with the six-field pattern, the severity slot picks up the first word
    of the message — which is how a healthy service came to report a 57% error
    rate against real production logs.
    """
    raw = (
        "2026-08-23T15:23:11.014415+00:00 lotor.dc3.crunchtools.com mcp-memory "
        "INFO INFO:httpx:HTTP Request: POST https://example.com"
    )
    parsed = parse_line(raw)
    assert parsed is not None
    assert parsed.severity == "INFO"
    assert parsed.source == "mcp-memory"
    assert parsed.program == "mcp-memory"
    assert parsed.message == "INFO:httpx:HTTP Request: POST https://example.com"


def test_six_field_line_still_wins_when_both_could_match() -> None:
    """Layout is decided by where a real severity sits, not by field count."""
    raw = "2026-08-23T10:00:00+00:00 host crunchtools.com httpd ERR AH00169: caught SIGTERM"
    parsed = parse_line(raw)
    assert parsed is not None
    assert parsed.severity == "ERR"
    assert parsed.program == "httpd"
    assert parsed.message == "AH00169: caught SIGTERM"


def test_legacy_line_whose_message_starts_with_a_severity_word() -> None:
    """A five-field line beginning 'INFO ...' must not be read as six fields."""
    raw = "2026-08-23T10:00:00+00:00 host mysvc WARNING INFO something happened"
    parsed = parse_line(raw)
    assert parsed is not None
    assert parsed.severity == "WARNING"
    assert parsed.message == "INFO something happened"
