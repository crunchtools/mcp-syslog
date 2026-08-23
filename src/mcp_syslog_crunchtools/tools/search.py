"""Search and grep tools."""

from __future__ import annotations

from ..parser import parse_time
from ..query import render, run_query
from ..reader import compile_pattern


def search(
    *,
    source: str | None = None,
    since: str = "1h",
    until: str | None = None,
    severity: str | None = None,
    pattern: str | None = None,
    program: str | None = None,
    limit: int | None = None,
) -> str:
    """Search collected logs by source, time, severity and pattern."""
    start = parse_time(since)
    end = parse_time(until) if until else None
    compiled = compile_pattern(pattern) if pattern else None
    sources = [source] if source else None

    result = run_query(
        sources=sources,
        start=start,
        end=end,
        severity=severity,
        pattern=compiled,
        program=program,
        limit=limit,
    )

    window = f"since {since}" + (f" until {until}" if until else "")
    scope = source or f"{len(result.sources_searched)} sources"
    filters = []
    if severity:
        filters.append(f"severity>={severity.upper()}")
    if pattern:
        filters.append(f"pattern={pattern!r}")
    if program:
        filters.append(f"program={program}")
    suffix = f" [{', '.join(filters)}]" if filters else ""

    header = f"{len(result.lines)} entries from {scope}, {window}{suffix}"
    return render(result, show_source=source is None, header=header)


def grep(
    pattern: str,
    *,
    source: str | None = None,
    since: str = "24h",
    severity: str | None = None,
    limit: int | None = None,
) -> str:
    """Regex search across all sources, or one named source."""
    return search(
        source=source,
        since=since,
        severity=severity,
        pattern=pattern,
        limit=limit,
    )
