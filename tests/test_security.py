"""Security tests.

Source names and regular expressions come straight from a model, which makes
them untrusted input used to build filesystem paths and to drive a regex engine.
These are the cases that matter most in this server.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from mcp_syslog_crunchtools.errors import InvalidPatternError, InvalidSourceError
from mcp_syslog_crunchtools.reader import MAX_PATTERN_LENGTH, compile_pattern, resolve_source_dir


@pytest.mark.parametrize(
    "hostile",
    [
        "../etc",
        "../../etc/passwd",
        "/etc/passwd",
        "..",
        ".",
        "",
        "mcp-memory/../../etc",
        "foo/bar",
        "foo\\bar",
    ],
)
def test_traversal_source_names_are_rejected(log_root: Path, hostile: str) -> None:
    """A source name must never resolve outside the log root."""
    with pytest.raises(InvalidSourceError):
        resolve_source_dir(hostile)


def test_symlink_escaping_the_root_is_rejected(log_root: Path, tmp_path: Path) -> None:
    """A symlink out of the tree is caught, which a check for '..' alone would miss."""
    secret = tmp_path / "secret"
    secret.mkdir()
    (secret / "2026-08-23.log").write_text("nothing to see", encoding="utf-8")
    (log_root / "escape").symlink_to(secret, target_is_directory=True)

    with pytest.raises(InvalidSourceError):
        resolve_source_dir("escape")


def test_legitimate_source_resolves(log_root: Path) -> None:
    resolved = resolve_source_dir("mcp-memory")
    assert resolved == (log_root / "mcp-memory").resolve()


def test_unknown_source_is_rejected(log_root: Path) -> None:
    with pytest.raises(InvalidSourceError):
        resolve_source_dir("no-such-service")


def test_overlong_pattern_is_rejected() -> None:
    """Bounds the blast radius of a pathological regex; Python's re has no timeout."""
    with pytest.raises(InvalidPatternError):
        compile_pattern("a" * (MAX_PATTERN_LENGTH + 1))


def test_invalid_regex_reports_cleanly() -> None:
    with pytest.raises(InvalidPatternError):
        compile_pattern("([unclosed")


def test_pattern_is_case_insensitive_by_default() -> None:
    assert compile_pattern("ERROR").search("an error occurred")
