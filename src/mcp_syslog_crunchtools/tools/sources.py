"""Sources tool — what can be queried."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from ..reader import DATE_FILE_RE, list_sources, resolve_source_dir

logger = logging.getLogger(__name__)


def sources(*, pattern: str | None = None, include_internal: bool = False) -> str:
    """List every source the collector has logs for.

    Discovery matters here: source names are container names, and a caller that
    guesses one wrong gets an empty result that looks exactly like a healthy
    service. Listing them removes the guess.
    """
    names = list_sources(include_internal=include_internal)

    if pattern:
        needle = pattern.lower()
        names = [name for name in names if needle in name.lower()]

    if not names:
        scope = f" matching {pattern!r}" if pattern else ""
        return f"No log sources{scope}."

    now = datetime.now(timezone.utc)
    rows = []
    for name in names:
        try:
            source_dir = resolve_source_dir(name)
        except Exception as exc:
            logger.debug("Skipping source %s: %s", name, exc)
            continue

        files = [f for f in source_dir.iterdir() if f.is_file() and DATE_FILE_RE.match(f.name)]
        if not files:
            continue
        newest = max(files, key=lambda f: f.stat().st_mtime)
        age_min = int((now.timestamp() - newest.stat().st_mtime) / 60)
        size_mb = sum(f.stat().st_size for f in files) / (1024 * 1024)
        rows.append((name, len(files), size_mb, age_min))

    lines = [
        f"{len(rows)} log source(s)" + (f" matching {pattern!r}" if pattern else ""),
        "",
        f"{'SOURCE':<38} {'DAYS':>5} {'SIZE':>9} {'LAST WRITE':>12}",
    ]
    for name, days, size_mb, age_min in rows:
        if age_min < 60:
            age = f"{age_min}m ago"
        elif age_min < 60 * 48:
            age = f"{age_min // 60}h ago"
        else:
            age = f"{age_min // 1440}d ago"
        lines.append(f"{name[:38]:<38} {days:>5} {size_mb:>8.1f}M {age:>12}")

    return "\n".join(lines)
