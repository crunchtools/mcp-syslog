# mcp-syslog-crunchtools Constitution

> **Version:** 1.1.0
> **Ratified:** 2026-08-23
> **Amended:** 2026-10-02
> **Status:** Active
> **Inherits:** [crunchtools/constitution](https://github.com/crunchtools/constitution) v1.21.0
> **Profile:** MCP Server

This file holds what is specific to mcp-syslog. The fleet rules and the MCP
Server profile (five-layer security model, two-layer tools, distribution
channels, transport modes, quality gates, Gourmand) apply at the inherited
version and are checked against this repo's files by `constitution.yml`. They
are not restated here.

## Threat Model Deviations

This server's threat model differs from the rest of the fleet: it holds no
credentials and makes no outbound calls. Its untrusted inputs are the tool
arguments, which come from a model and are used to build filesystem paths and
to drive a regex engine.

- **No credentials, no `SecretStr`.** The server reads files from a read-only
  bind mount. The absence of `SecretStr` is deliberate: there is no secret to
  wrap. Should the server ever gain a credential, `SecretStr` becomes
  mandatory per the profile.
- **Path containment.** Source names are resolved and then confirmed to still
  be inside the log root. That catches traversal, absolute paths and symlinks
  pointing out of the tree; a string check for `..` catches only the first.
- **Regex bounding.** Caller-supplied regular expressions are length-capped.
  Python's `re` has no execution timeout, so bounding the input is the
  available defence.
- **Strict time parsing.** Time arguments are rejected rather than coerced.
- **No Pydantic tool models.** Every argument is a scalar validated at the
  point of use (path resolution, regex compilation, timestamp parsing), where
  the check has the context to be meaningful. Pydantic remains a dependency
  and MUST be used if any tool grows a structured argument.
- **No HTTP client.** Resource bounding replaces API hardening: every tool
  caps both results returned (`SYSLOG_MAX_RESULTS`, default 200) and lines
  scanned (`SYSLOG_SCAN_LIMIT`, default 2000000), and reports when either cap
  was hit. Time-bounded queries open only the files whose date bucket overlaps
  the range. Parsing, reading and gzip decompression use the standard library
  only.
- **Read-only mount.** The log root (`SYSLOG_LOG_ROOT`, default `/logs`) MUST
  be mounted `:ro`, so a bug cannot destroy the forensic record the server
  exists to protect.

## Honest Results

A truncated or aborted result MUST say so. The server exists to inform
remediation decisions, and a caller that cannot tell "no errors occurred" from
"I stopped looking" will act on the wrong conclusion. `QueryResult` carries
`truncated`, `scan_limit_hit` and `unparsed`, and `render()` surfaces all
three. Tests assert each; a silently truncated result is a correctness bug.

## Severity Is Reported, Not Interpreted

Podman records anything written to container stderr at syslog priority `err`,
so services logging routine INFO to stderr appear as ERR. The server reports
what the journal says and states the caveat in its MCP instructions; it does
not second-guess severities from message text, which would be a heuristic
masquerading as data.

Filtering keeps unrecognised severities (hiding a line you do not understand
is worse than showing it), but `syslog_stats_tool` uses a strict lookup when
counting errors. Conflating the two produced a 57% error rate for healthy
services against real logs.

## Log Format Ownership

The collector, [crunchtools/syslog](https://github.com/crunchtools/syslog),
owns the format. A change starts in its `config/rsyslog.conf` and is mirrored
here, never the reverse. The collector emitted five fields before 2026-08-23
and six after; lines stay in retention for 90 days. Support for a previous
format, and fixture tests for it, MUST be retained until it has aged out of
retention. Dropping a format still inside retention is a MAJOR change.

`tests/test_security.py` covers path traversal, absolute paths, symlinks
escaping the log root and regex bounding: the only genuinely untrusted input
this server has. Tests build a log root under `tmp_path`; nothing touches the
real collector.

## Instance

| Context | Name |
|---------|------|
| GitHub repo | `crunchtools/mcp-syslog` |
| PyPI package | `mcp-syslog-crunchtools` |
| Python module | `mcp_syslog_crunchtools` |
| Container image | `quay.io/crunchtools/mcp-syslog` |
| Tool names | `syslog_<verb>_tool` |
| HTTP port | 8027 (`streamable-http`, behind the Trentina gateway) |

Nagios check definitions live in `deploy/nagios/`.
[crunchtools/mcp-nagios](https://github.com/crunchtools/mcp-nagios) is the
alerting half of the same triage loop.

## History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-08-23 | Initial constitution (RT #1460, Phase 4) |
| 1.1.0 | 2026-10-02 | Manifest under constitution v1.18.0: profile restatement removed, mcp-syslog threat model and format rules kept |
