"""Test fixtures for the Syslog MCP server."""

from __future__ import annotations

import gzip
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

from mcp_syslog_crunchtools import config as config_mod


@pytest.fixture(autouse=True)
def _reset_config_singleton() -> Iterator[None]:
    config_mod._config = None
    yield
    config_mod._config = None


def write_log(root: Path, source: str, day: str, lines: list[str], *, gz: bool = False) -> Path:
    """Write a day's log file for a source in the collector's format."""
    source_dir = root / source
    source_dir.mkdir(parents=True, exist_ok=True)
    body = "".join(line if line.endswith("\n") else line + "\n" for line in lines)
    if gz:
        path = source_dir / f"{day}.log.gz"
        with gzip.open(path, "wt", encoding="utf-8") as handle:
            handle.write(body)
    else:
        path = source_dir / f"{day}.log"
        path.write_text(body, encoding="utf-8")
    return path


def line(
    timestamp: str,
    source: str,
    message: str,
    *,
    host: str = "lotor.dc3.crunchtools.com",
    program: str | None = None,
    severity: str = "INFO",
) -> str:
    """Build one record in the collector's six-field format."""
    return f"{timestamp} {host} {source} {program or source} {severity} {message}"


@pytest.fixture
def log_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A populated log root wired up as SYSLOG_LOG_ROOT."""
    root = tmp_path / "logs"
    root.mkdir()

    write_log(
        root,
        "mcp-memory",
        "2026-08-23",
        [
            line("2026-08-23T10:00:00+00:00", "mcp-memory", "started up"),
            line("2026-08-23T10:05:00+00:00", "mcp-memory", "connection refused", severity="ERR"),
            line("2026-08-23T10:06:00+00:00", "mcp-memory", "retrying request"),
            line("2026-08-23T10:10:00+00:00", "mcp-memory", "database is gone", severity="CRIT"),
        ],
    )
    write_log(
        root,
        "crunchtools.com",
        "2026-08-23",
        [
            line(
                "2026-08-23T10:05:30+00:00",
                "crunchtools.com",
                "AH00169: caught SIGTERM",
                program="httpd",
                severity="WARNING",
            ),
            line(
                "2026-08-23T10:07:00+00:00",
                "crunchtools.com",
                "pool exhausted",
                program="php-fpm",
                severity="ERR",
            ),
        ],
    )
    # A compressed older day, to prove rotated files are still searchable.
    write_log(
        root,
        "mcp-memory",
        "2026-08-21",
        [line("2026-08-21T09:00:00+00:00", "mcp-memory", "ancient history")],
        gz=True,
    )
    (root / "_collector").mkdir()
    (root / "_collector" / "2026-08-23.log").write_text(
        line("2026-08-23T10:00:00+00:00", "_collector", "stats"), encoding="utf-8"
    )

    monkeypatch.setenv("SYSLOG_LOG_ROOT", str(root))
    return root
