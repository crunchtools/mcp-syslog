"""Locating and reading the collector's log files.

Layout written by the collector:

    <log_root>/<source>/<YYYY-MM-DD>.log        recent days
    <log_root>/<source>/<YYYY-MM-DD>.log.gz     compressed after 2 days

Because the day is in the filename, a time-bounded query only has to open the
files whose date falls in range. That is the difference between reading ten
minutes of logs and reading ninety days of them.
"""

from __future__ import annotations

import gzip
import re
from datetime import date, timedelta
from typing import TYPE_CHECKING

from .config import get_config
from .errors import InvalidPatternError, InvalidSourceError

if TYPE_CHECKING:
    import io
    from collections.abc import Iterator
    from datetime import datetime
    from pathlib import Path

DATE_FILE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.log(\.gz)?$")

# The collector's own statistics live here. Useful, but not a service, so it is
# hidden from source listings unless asked for by name.
COLLECTOR_DIR = "_collector"

# A regex long enough to be pathological is almost never a real query, and
# Python's re offers no execution timeout to fall back on.
MAX_PATTERN_LENGTH = 500


def list_sources(*, include_internal: bool = False) -> list[str]:
    """Every source that has at least one log file, alphabetically."""
    root = get_config().log_root
    sources = []
    for entry in root.iterdir():
        if not entry.is_dir():
            continue
        if entry.name == COLLECTOR_DIR and not include_internal:
            continue
        if any(DATE_FILE_RE.match(f.name) for f in entry.iterdir() if f.is_file()):
            sources.append(entry.name)
    return sorted(sources)


def resolve_source_dir(source: str) -> Path:
    """Resolve a source name to its directory, refusing anything outside the root.

    ``source`` comes from the model. Resolving and then confirming the result is
    still under the log root catches traversal (``../../etc``), absolute paths,
    and symlinks pointing out of the tree, which a string check on ``..`` alone
    would miss.
    """
    root = get_config().log_root
    if not source or "/" in source or "\\" in source or source in {".", ".."}:
        raise InvalidSourceError(source)

    candidate = (root / source).resolve()
    if candidate != root and root not in candidate.parents:
        raise InvalidSourceError(source)
    if not candidate.is_dir():
        raise InvalidSourceError(source)
    return candidate


def files_for_range(
    source_dir: Path,
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[Path]:
    """Log files for a source whose date bucket overlaps [start, end], oldest first.

    The bucket is the collector's *receipt* date. A record can carry a timestamp
    slightly outside its own file's day — a message received at 23:59:59.9 and
    stamped a moment later, for instance — so the range is widened by a day at
    each end. Callers still filter on the parsed timestamp; this only decides
    which files are worth opening.
    """
    start_date = (start.date() - timedelta(days=1)) if start else date.min
    end_date = (end.date() + timedelta(days=1)) if end else date.max

    selected: list[tuple[date, Path]] = []
    for path in source_dir.iterdir():
        if not path.is_file():
            continue
        match = DATE_FILE_RE.match(path.name)
        if not match:
            continue
        try:
            file_date = date.fromisoformat(match.group(1))
        except ValueError:
            continue
        if start_date <= file_date <= end_date:
            selected.append((file_date, path))

    return [path for _, path in sorted(selected)]


def open_log(path: Path) -> io.TextIOBase:
    """Open a log file, transparently decompressing rotated ones."""
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return path.open("r", encoding="utf-8", errors="replace")


def iter_lines(paths: list[Path]) -> Iterator[str]:
    """Yield raw lines across files in order."""
    for path in paths:
        try:
            with open_log(path) as handle:
                yield from handle
        except OSError:
            # A file rotated or compressed out from under us mid-read is normal
            # here; skipping it beats failing the whole query.
            continue


def tail_lines(paths: list[Path], limit: int) -> list[str]:
    """Last ``limit`` lines across files, oldest first.

    Walks files newest-first and stops as soon as it has enough, so tailing a
    chatty source does not read the whole of yesterday to return ten lines. The
    final file is still read forward — seeking backwards through a gzip stream
    is not possible, and the uncompressed daily files are small enough that it
    would not pay for itself.
    """
    collected: list[str] = []
    for path in reversed(paths):
        try:
            with open_log(path) as handle:
                lines = handle.readlines()
        except OSError:
            continue
        needed = limit - len(collected)
        collected = lines[-needed:] + collected
        if len(collected) >= limit:
            break
    return collected[-limit:]


def compile_pattern(pattern: str, *, ignore_case: bool = True) -> re.Pattern[str]:
    """Compile a caller-supplied regex, rejecting the ones that are trouble."""
    if len(pattern) > MAX_PATTERN_LENGTH:
        raise InvalidPatternError(
            pattern[:60] + "...",
            f"longer than {MAX_PATTERN_LENGTH} characters",
        )
    flags = re.IGNORECASE if ignore_case else 0
    try:
        return re.compile(pattern, flags)
    except re.error as exc:
        raise InvalidPatternError(pattern, str(exc)) from exc
