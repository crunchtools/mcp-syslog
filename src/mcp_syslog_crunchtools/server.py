"""FastMCP server for querying centrally collected logs."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastmcp import FastMCP

from .tools import context, grep, search, sources, stats, tail

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_mcp: FastMCP) -> AsyncIterator[None]:
    logger.info("Starting Syslog MCP server")
    yield
    logger.info("Syslog MCP server stopped")


mcp = FastMCP(
    name="mcp-syslog-crunchtools",
    version="0.1.0",
    lifespan=lifespan,
    instructions=(
        "MCP server for logs collected centrally from crunchtools infrastructure. "
        "Use this to find out WHY a service failed before deciding how to fix it.\n\n"
        "A source is normally a container name. If you are unsure of the exact name, "
        "call syslog_sources_tool first — querying a name that does not exist returns "
        "an empty result that looks identical to a healthy service.\n\n"
        "Typical triage: nagios_current_problems_tool to see what is broken, then "
        "syslog_search_tool(source=..., severity='ERR', since='15m') to see why, then "
        "syslog_context_tool around the failure time to see what else was happening.\n\n"
        "IMPORTANT — severity is not the same as badness. Podman records anything a "
        "container writes to stderr at syslog priority 'err', and many services log "
        "routine INFO to stderr. So a source can sit at a 60% ERR rate while being "
        "perfectly healthy. Read the message text before concluding something is "
        "wrong, and prefer a change in the error rate over its absolute value.\n\n"
        "Every tool bounds its own output and says so when a result is truncated or "
        "the scan limit was hit. Treat those notices as meaningful: an empty result "
        "from an incomplete scan is not evidence that nothing happened."
    ),
)


@mcp.tool()
async def syslog_sources_tool(
    pattern: str | None = None,
    include_internal: bool = False,
) -> str:
    """List log sources available to query, with size and last-write time.

    Args:
        pattern: Optional case-insensitive substring to filter source names.
        include_internal: Include the collector's own '_collector' statistics.

    Returns:
        Table of sources with day count, total size, and how long since the last write.
    """
    return sources(pattern=pattern, include_internal=include_internal)


@mcp.tool()
async def syslog_search_tool(
    *,
    source: str | None = None,
    since: str = "1h",
    until: str | None = None,
    severity: str | None = None,
    pattern: str | None = None,
    program: str | None = None,
    limit: int | None = None,
) -> str:
    """Search collected logs by source, time window, severity and pattern.

    Args:
        source: Container or service name. Omit to search every source.
        since: Start of the window — relative ('15m', '2h', '3d') or ISO-8601.
        until: End of the window. Omit for "up to now".
        severity: Minimum severity: EMERG, ALERT, CRIT, ERR, WARNING, NOTICE, INFO, DEBUG.
            'ERR' returns ERR and anything more severe.
        pattern: Optional case-insensitive regular expression matched against the message.
        program: Restrict to one program within the source (e.g. 'httpd' inside a web container).
        limit: Maximum entries to return.

    Returns:
        Matching entries, newest kept when truncated, with a note if the result is incomplete.
    """
    return search(
        source=source,
        since=since,
        until=until,
        severity=severity,
        pattern=pattern,
        program=program,
        limit=limit,
    )


@mcp.tool()
async def syslog_grep_tool(
    pattern: str,
    source: str | None = None,
    since: str = "24h",
    severity: str | None = None,
    limit: int | None = None,
) -> str:
    """Regex search across all sources, or within one named source.

    Args:
        pattern: Case-insensitive regular expression matched against the message.
        source: Restrict to one source. Omit to search the whole fleet.
        since: How far back to search — relative ('15m', '2h', '3d') or ISO-8601.
        severity: Optional minimum severity.
        limit: Maximum entries to return.

    Returns:
        Matching entries with their source, plus a note if the result is incomplete.
    """
    return grep(pattern=pattern, source=source, since=since, severity=severity, limit=limit)


@mcp.tool()
async def syslog_tail_tool(
    source: str,
    limit: int = 50,
    severity: str | None = None,
) -> str:
    """Return the most recent entries for one source.

    Args:
        source: Container or service name.
        limit: Number of entries to return.
        severity: Optional minimum severity.

    Returns:
        The most recent entries, oldest first.
    """
    return tail(source=source, limit=limit, severity=severity)


@mcp.tool()
async def syslog_context_tool(
    timestamp: str,
    *,
    source: str | None = None,
    before_seconds: int = 60,
    after_seconds: int = 60,
    severity: str | None = None,
    limit: int | None = None,
) -> str:
    """Return log entries surrounding a specific moment.

    Use this after an alert names a time. Omitting source spans the whole fleet,
    which is how a failure gets correlated with whatever else was happening.

    Args:
        timestamp: The moment of interest — ISO-8601, or relative like '30m' ago.
        source: Restrict to one source. Omit to span all sources.
        before_seconds: How far back from the timestamp to include.
        after_seconds: How far forward from the timestamp to include.
        severity: Optional minimum severity.
        limit: Maximum entries to return.

    Returns:
        Entries in the window, oldest first.
    """
    return context(
        timestamp=timestamp,
        source=source,
        before_seconds=before_seconds,
        after_seconds=after_seconds,
        severity=severity,
        limit=limit,
    )


@mcp.tool()
async def syslog_stats_tool(
    since: str = "1h",
    source: str | None = None,
    top: int = 20,
) -> str:
    """Summarise log volume and error rate per source.

    Args:
        since: Window to summarise — relative ('1h', '24h') or ISO-8601.
        source: Restrict to one source. Omit to cover every source.
        top: How many sources to list, ranked by volume.

    Returns:
        Per-source line counts, error counts and error rates, plus a severity breakdown.
    """
    return stats(since=since, source=source, top=top)
