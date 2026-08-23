"""Stats tool — volume and error rates per source."""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..config import get_config
from ..parser import SEVERITY_ORDER, parse_line, parse_time
from ..reader import files_for_range, iter_lines, list_sources, resolve_source_dir

if TYPE_CHECKING:
    from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class _Counts:
    totals: Counter[str] = field(default_factory=Counter)
    errors: Counter[str] = field(default_factory=Counter)
    severities: Counter[str] = field(default_factory=Counter)
    scanned: int = 0
    scan_limit_hit: bool = False


def _collect(targets: list[str], start: datetime) -> _Counts:
    """Tally lines, errors and severities across the selected sources."""
    config = get_config()
    counts = _Counts()

    for name in targets:
        try:
            source_dir = resolve_source_dir(name)
        except Exception as exc:
            logger.debug("Skipping source %s: %s", name, exc)
            continue

        for raw in iter_lines(files_for_range(source_dir, start, None)):
            if counts.scanned >= config.scan_limit:
                counts.scan_limit_hit = True
                return counts
            counts.scanned += 1

            line = parse_line(raw)
            if line is None or line.timestamp < start:
                continue

            counts.totals[name] += 1
            counts.severities[line.severity] += 1
            # Strict lookup, unlike the filtering path. severity_at_least() keeps
            # unrecognised severities so a line you do not understand is never
            # hidden, but counting them as errors would report a 57% error rate
            # for a perfectly healthy service.
            level = SEVERITY_ORDER.get(line.severity)
            if level is not None and level <= SEVERITY_ORDER["ERR"]:
                counts.errors[name] += 1

    return counts


def stats(*, since: str = "1h", source: str | None = None, top: int = 20) -> str:
    """Summarise log volume and error rate.

    The point is triage: which service is loudest, and which is actually
    unhealthy. Those are different questions — a service can be quiet and broken,
    or noisy and fine — so error *rate* is reported alongside volume rather than
    ranking on volume alone.
    """
    start = parse_time(since)
    targets = [source] if source else list_sources()
    counts = _collect(targets, start)

    if not counts.totals:
        return f"No log entries since {since} across {len(targets)} source(s)."

    summary = (
        f"Log volume since {since} — {sum(counts.totals.values()):,} entries "
        f"across {len(counts.totals)} active source(s)"
    )
    lines = [
        summary,
        "",
        f"{'SOURCE':<38} {'LINES':>10} {'ERRORS':>8} {'RATE':>7}",
    ]
    for name, count in counts.totals.most_common(top):
        err = counts.errors.get(name, 0)
        rate = (err / count * 100) if count else 0.0
        lines.append(f"{name[:38]:<38} {count:>10,} {err:>8,} {rate:>6.1f}%")

    if len(counts.totals) > top:
        lines.append(f"... and {len(counts.totals) - top} more source(s)")

    breakdown = ", ".join(
        f"{sev}={cnt:,}" for sev, cnt in sorted(counts.severities.items(), key=lambda kv: -kv[1])
    )
    lines.extend(["", f"By severity: {breakdown}"])

    noisy = [name for name, count in counts.errors.most_common(5) if count]
    if noisy:
        joined = ", ".join(noisy)
        lines.extend(["", f"Sources reporting errors: {joined}"])

    if counts.scan_limit_hit:
        warning = (
            f"[!] Stopped after the {counts.scanned:,}-line scan limit — these totals are "
            "INCOMPLETE and undercount the sources scanned last. Use a shorter window."
        )
        lines.extend(["", warning])

    return "\n".join(lines)
