"""Context tool — what surrounded a moment in time."""

from __future__ import annotations

from datetime import timedelta

from ..parser import parse_time
from ..query import render, run_query


def context(
    timestamp: str,
    *,
    source: str | None = None,
    before_seconds: int = 60,
    after_seconds: int = 60,
    severity: str | None = None,
    limit: int | None = None,
) -> str:
    """Return log entries surrounding a point in time.

    Built for the question that follows an alert: Nagios says a service went
    critical at 03:14, so show everything around 03:14. Without a source it spans
    the whole fleet, which is how a failure gets tied to whatever else was
    happening on the box at that instant.
    """
    center = parse_time(timestamp)
    start = center - timedelta(seconds=max(0, before_seconds))
    end = center + timedelta(seconds=max(0, after_seconds))

    result = run_query(
        sources=[source] if source else None,
        start=start,
        end=end,
        severity=severity,
        limit=limit,
        newest_first=False,
    )

    scope = source or f"{len(result.sources_searched)} sources"
    header = (
        f"{len(result.lines)} entries from {scope} between "
        f"{start:%Y-%m-%d %H:%M:%S} and {end:%Y-%m-%d %H:%M:%S} "
        f"(±{before_seconds}s/{after_seconds}s around {center:%Y-%m-%d %H:%M:%S})"
    )
    return render(result, show_source=source is None, header=header)
