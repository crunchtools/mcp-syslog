"""Error types for the Syslog MCP server."""

from fastmcp.exceptions import ToolError


class ConfigurationError(ToolError):
    """Raised when required configuration is missing or invalid."""


class InvalidSourceError(ToolError):
    """Raised when a source name does not resolve inside the log root.

    Source names arrive from the model, so they are untrusted input used to build
    a filesystem path. Anything that escapes the log root is rejected outright.
    """

    def __init__(self, source: str) -> None:
        super().__init__(
            f"Invalid log source {source!r}. Use syslog_sources_tool to list valid sources."
        )


class InvalidPatternError(ToolError):
    """Raised when a caller-supplied regular expression cannot be used."""

    def __init__(self, pattern: str, reason: str) -> None:
        super().__init__(f"Invalid pattern {pattern!r}: {reason}")


class InvalidTimeRangeError(ToolError):
    """Raised when a time argument cannot be interpreted."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Could not parse time {value!r}. Use an ISO-8601 timestamp "
            "(2026-08-23T15:00:00+00:00) or a relative offset like '15m', '2h', '3d'."
        )
