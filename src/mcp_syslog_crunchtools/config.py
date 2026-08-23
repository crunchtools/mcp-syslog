"""Configuration for the Syslog MCP server.

There are no credentials here. The server reads log files off a read-only bind
mount, so its only configuration is where that mount is and how much output it is
allowed to return.
"""

import logging
import os
from pathlib import Path

from .errors import ConfigurationError

logger = logging.getLogger(__name__)

# Every tool caps its own output. Logs are unbounded and this output lands in a
# model's context window, so an uncapped query would blow the budget on a single
# call and crowd out the reasoning it was meant to support.
DEFAULT_MAX_RESULTS = 200
HARD_MAX_RESULTS = 2000

# Ceiling on lines examined per call, independent of how many match. This is what
# keeps a broad regex over 90 days of logs from pinning a CPU, and it also bounds
# the damage from a pathological pattern, since Python's re has no timeout.
DEFAULT_SCAN_LIMIT = 2_000_000


class Config:
    """Configuration from environment variables."""

    def __init__(self) -> None:
        root = os.environ.get("SYSLOG_LOG_ROOT", "/logs")
        path = Path(root)
        if not path.is_dir():
            raise ConfigurationError(
                f"SYSLOG_LOG_ROOT {root!r} is not a directory. "
                "Mount the collector's log root into this container."
            )
        self._log_root = path.resolve()

        self._max_results = _positive_int("SYSLOG_MAX_RESULTS", DEFAULT_MAX_RESULTS)
        self._scan_limit = _positive_int("SYSLOG_SCAN_LIMIT", DEFAULT_SCAN_LIMIT)

        logger.info("Configuration loaded, log root %s", self._log_root)

    @property
    def log_root(self) -> Path:
        return self._log_root

    @property
    def max_results(self) -> int:
        return self._max_results

    @property
    def scan_limit(self) -> int:
        return self._scan_limit

    def __repr__(self) -> str:
        return f"Config(log_root={self._log_root!r}, max_results={self._max_results})"


def _positive_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer, got {raw!r}") from exc
    if value <= 0:
        raise ConfigurationError(f"{name} must be positive, got {value}")
    return value


_config: Config | None = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config()
    return _config
