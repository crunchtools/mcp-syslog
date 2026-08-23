"""Tool behaviour tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from mcp_syslog_crunchtools import config as config_mod
from mcp_syslog_crunchtools.tools import context, grep, search, sources, stats, tail

from .conftest import line, write_log

# Every fixture entry sits on 2026-08-23, so queries use an absolute start rather
# than a relative one that would drift past the data as the suite ages.
SINCE = "2026-08-23T00:00:00+00:00"


def test_sources_lists_services_and_hides_collector(log_root: Path) -> None:
    out = sources()
    assert "mcp-memory" in out
    assert "crunchtools.com" in out
    assert "_collector" not in out


def test_sources_can_include_collector(log_root: Path) -> None:
    assert "_collector" in sources(include_internal=True)


def test_sources_filter(log_root: Path) -> None:
    out = sources(pattern="mcp")
    assert "mcp-memory" in out
    assert "crunchtools.com" not in out


def test_search_finds_entries_in_window(log_root: Path) -> None:
    out = search(source="mcp-memory", since=SINCE)
    assert "started up" in out
    assert "connection refused" in out


def test_search_severity_filter_is_at_least(log_root: Path) -> None:
    out = search(source="mcp-memory", since=SINCE, severity="ERR")
    assert "connection refused" in out  # ERR
    assert "database is gone" in out  # CRIT, more severe
    assert "started up" not in out  # INFO


def test_search_across_all_sources(log_root: Path) -> None:
    out = search(since=SINCE, severity="ERR")
    assert "connection refused" in out
    assert "pool exhausted" in out


def test_search_pattern_filter(log_root: Path) -> None:
    out = search(source="mcp-memory", since=SINCE, pattern="refused")
    assert "connection refused" in out
    assert "started up" not in out


def test_search_program_filter_distinguishes_within_a_container(log_root: Path) -> None:
    """The reason program is its own field: httpd and php-fpm share a source."""
    out = search(source="crunchtools.com", since=SINCE, program="php-fpm")
    assert "pool exhausted" in out
    assert "SIGTERM" not in out


def test_search_reads_compressed_rotated_files(log_root: Path) -> None:
    out = search(source="mcp-memory", since="2026-08-20T00:00:00+00:00")
    assert "ancient history" in out


def test_search_empty_result_is_explicit(log_root: Path) -> None:
    out = search(source="mcp-memory", since=SINCE, pattern="nothing-matches-this")
    assert "No matching log entries" in out
    assert "Scanned" in out


def test_grep_searches_whole_fleet(log_root: Path) -> None:
    out = grep(pattern="pool exhausted", since=SINCE)
    assert "pool exhausted" in out
    assert "crunchtools.com" in out


def test_tail_returns_most_recent(log_root: Path) -> None:
    out = tail("mcp-memory", limit=2)
    assert "database is gone" in out
    assert "started up" not in out


def test_tail_severity_filter(log_root: Path) -> None:
    out = tail("mcp-memory", limit=10, severity="CRIT")
    assert "database is gone" in out
    assert "retrying request" not in out


def test_tail_unknown_source_raises(log_root: Path) -> None:
    from mcp_syslog_crunchtools.errors import InvalidSourceError

    with pytest.raises(InvalidSourceError):
        tail("no-such-service")


def test_context_correlates_across_sources(log_root: Path) -> None:
    """The payoff: one timestamp, everything the fleet was saying around it."""
    out = context("2026-08-23T10:05:30+00:00", before_seconds=60, after_seconds=120)
    assert "connection refused" in out  # mcp-memory at 10:05:00
    assert "SIGTERM" in out  # crunchtools.com at 10:05:30
    assert "pool exhausted" in out  # crunchtools.com at 10:07:00
    assert "database is gone" not in out  # 10:10:00, outside the window


def test_context_window_excludes_outside_entries(log_root: Path) -> None:
    out = context(
        "2026-08-23T10:00:00+00:00", source="mcp-memory", before_seconds=10, after_seconds=10
    )
    assert "started up" in out
    assert "connection refused" not in out


def test_stats_reports_volume_and_error_rate(log_root: Path) -> None:
    out = stats(since=SINCE)
    assert "mcp-memory" in out
    assert "crunchtools.com" in out
    assert "By severity" in out
    assert "Sources reporting errors" in out


def test_stats_counts_errors_at_or_above_err(log_root: Path) -> None:
    out = stats(since=SINCE, source="mcp-memory")
    # ERR + CRIT out of 4 lines.
    assert "50.0%" in out


def test_truncation_is_reported(log_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty or short result must never be mistaken for 'nothing happened'."""
    monkeypatch.setenv("SYSLOG_MAX_RESULTS", "2")
    config_mod._config = None

    out = search(source="mcp-memory", since=SINCE)
    assert "[!]" in out
    assert "more recent matches only" in out or "there were more" in out


def test_scan_limit_is_reported_as_incomplete(
    log_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SYSLOG_SCAN_LIMIT", "1")
    config_mod._config = None

    out = search(source="mcp-memory", since=SINCE)
    assert "INCOMPLETE" in out


def test_unparsed_lines_are_counted_not_silently_dropped(
    log_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_log(
        log_root,
        "broken-source",
        "2026-08-23",
        [
            "garbage line with no structure at all",
            line("2026-08-23T10:00:00+00:00", "broken-source", "a good line"),
        ],
    )
    out = search(source="broken-source", since=SINCE)
    assert "a good line" in out
    assert "did not match the expected log format" in out


def test_unknown_severity_is_not_counted_as_an_error(
    log_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Filtering keeps unknown severities; counting must not treat them as errors."""
    write_log(
        log_root,
        "odd-severity",
        "2026-08-23",
        [
            line("2026-08-23T10:00:00+00:00", "odd-severity", "a", severity="WEIRD"),
            line("2026-08-23T10:00:01+00:00", "odd-severity", "b", severity="WEIRD"),
        ],
    )
    out = stats(since=SINCE, source="odd-severity")
    assert "0.0%" in out
    assert "Sources reporting errors" not in out
