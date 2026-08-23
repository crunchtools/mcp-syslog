"""The shared query path behind the tools."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .config import get_config
from .parser import LogLine, parse_line, severity_at_least
from .reader import files_for_range, iter_lines, list_sources, resolve_source_dir

if TYPE_CHECKING:
    import re
    from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class QueryResult:
    """Matching lines plus what it took to find them.

    ``scanned`` and ``truncated`` are part of the answer, not bookkeeping. A
    caller that cannot tell "no errors occurred" from "I stopped looking" will
    draw the wrong conclusion from an empty result, and this server exists to
    inform remediation decisions.
    """

    lines: list[LogLine] = field(default_factory=list)
    scanned: int = 0
    truncated: bool = False
    scan_limit_hit: bool = False
    sources_searched: list[str] = field(default_factory=list)
    unparsed: int = 0


def _passes_filters(
    line: LogLine,
    *,
    start: datetime | None,
    end: datetime | None,
    severity: str | None,
    pattern: re.Pattern[str] | None,
    program: str | None,
) -> bool:
    """Whether one parsed record satisfies every active filter."""
    if start is not None and line.timestamp < start:
        return False
    if end is not None and line.timestamp > end:
        return False
    if severity is not None and not severity_at_least(line.severity, severity):
        return False
    if program is not None and line.program != program:
        return False
    return not (pattern is not None and not pattern.search(line.message))


def run_query(
    *,
    sources: list[str] | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    severity: str | None = None,
    pattern: re.Pattern[str] | None = None,
    program: str | None = None,
    limit: int | None = None,
    newest_first: bool = True,
) -> QueryResult:
    """Scan the selected sources and return matching records."""
    config = get_config()
    max_results = min(limit or config.max_results, config.max_results)

    targets = sources if sources else list_sources()
    result = QueryResult(sources_searched=list(targets))

    for source in targets:
        try:
            source_dir = resolve_source_dir(source)
        except Exception as exc:
            # A source listed a moment ago can disappear when retention runs.
            logger.debug("Skipping source %s: %s", source, exc)
            continue

        for raw in iter_lines(files_for_range(source_dir, start, end)):
            if result.scanned >= config.scan_limit:
                result.scan_limit_hit = True
                break
            result.scanned += 1

            line = parse_line(raw)
            if line is None:
                result.unparsed += 1
                continue
            if _passes_filters(
                line,
                start=start,
                end=end,
                severity=severity,
                pattern=pattern,
                program=program,
            ):
                result.lines.append(line)

        if result.scan_limit_hit:
            break

    result.lines.sort(key=lambda item: item.timestamp)

    if len(result.lines) > max_results:
        result.truncated = True
        # Keep the newest when truncating: a caller looking at a live failure
        # wants what just happened, not the oldest matches in the window.
        result.lines = result.lines[-max_results:] if newest_first else result.lines[:max_results]

    return result


def render(result: QueryResult, *, show_source: bool = True, header: str = "") -> str:
    """Render a result for the model, including why it might be incomplete."""
    parts: list[str] = []
    if header:
        parts.append(header)

    if not result.lines:
        parts.append(
            f"No matching log entries. Scanned {result.scanned:,} lines across "
            f"{len(result.sources_searched)} source(s)."
        )
    else:
        parts.append("\n".join(line.format(show_source=show_source) for line in result.lines))

    notes: list[str] = []
    if result.truncated:
        notes.append(
            f"Showing the {len(result.lines)} most recent matches only — there were more. "
            "Narrow the time range or add a pattern."
        )
    if result.scan_limit_hit:
        notes.append(
            f"Stopped after the {result.scanned:,}-line scan limit, so this result is "
            "INCOMPLETE and an empty or short result does not mean nothing happened. "
            "Narrow the time range or name specific sources."
        )
    if result.unparsed:
        notes.append(f"{result.unparsed:,} line(s) did not match the expected log format.")

    if notes:
        parts.append("\n".join(f"[!] {note}" for note in notes))

    return "\n\n".join(parts)
