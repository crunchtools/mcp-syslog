"""Tail tool — the most recent lines for one source."""

from __future__ import annotations

from ..config import get_config
from ..parser import parse_line
from ..reader import files_for_range, resolve_source_dir, tail_lines


def tail(source: str, *, limit: int = 50, severity: str | None = None) -> str:
    """Return the most recent entries for a source.

    Deliberately reads backwards from the newest file rather than going through
    the shared query path: a tail should stay cheap on a source producing
    hundreds of thousands of lines a day.
    """
    config = get_config()
    count = max(1, min(limit, config.max_results))

    source_dir = resolve_source_dir(source)
    paths = files_for_range(source_dir)
    if not paths:
        return f"No log files for source {source!r}."

    # Over-read when filtering, since severity is applied after the fact and most
    # lines in a healthy service are INFO.
    raw_limit = count * 20 if severity else count
    raw_limit = min(raw_limit, 100_000)

    lines = []
    for raw in tail_lines(paths, raw_limit):
        parsed = parse_line(raw)
        if parsed is None:
            continue
        if severity is not None:
            from ..parser import severity_at_least

            if not severity_at_least(parsed.severity, severity):
                continue
        lines.append(parsed)

    shown = lines[-count:]
    if not shown:
        scope = f" at severity>={severity.upper()}" if severity else ""
        return f"No entries for {source!r}{scope} in the most recent {raw_limit:,} lines."

    header = f"Last {len(shown)} entries for {source}"
    if severity:
        header += f" at severity>={severity.upper()}"
    body = "\n".join(line.format(show_source=False) for line in shown)
    return f"{header}\n{body}"
