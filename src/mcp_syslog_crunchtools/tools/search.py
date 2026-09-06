"""Search tool — regex and filter queries across sources."""

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

    matches = run_query(
        sources=sources,
        start=start,
        end=end,
        severity=severity,
        pattern=compiled,
        program=program,
        limit=limit,
    )

    window = f"since {since}" + (f" until {until}" if until else "")
    scope = source or f"{len(matches.sources_searched)} sources"
    filters = []
    if severity:
        filters.append(f"severity>={severity.upper()}")
    if pattern:
        filters.append(f"pattern={pattern!r}")
    if program:
        filters.append(f"program={program}")
    suffix = f" [{', '.join(filters)}]" if filters else ""

    header = f"{len(matches.lines)} entries from {scope}, {window}{suffix}"
    return render(matches, show_source=source is None, header=header)
