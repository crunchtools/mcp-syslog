# mcp-syslog-crunchtools Constitution

> **Version:** 1.0.0
> **Ratified:** 2026-08-23
> **Status:** Active
> **Inherits:** [crunchtools/constitution](https://github.com/crunchtools/constitution) v1.10.0
> **Profile:** MCP Server

---

## I. Core Principles

### 1. Five-Layer Security Model

This server's threat model differs from the rest of the fleet: it holds no
credentials and makes no outbound calls. Its untrusted inputs are the *tool
arguments*, which come from a model and are used to build filesystem paths and to
drive a regex engine.

**Layer 1 — Credential Protection:**
- No credentials exist. The server reads files from a read-only bind mount.
- `SecretStr` is therefore not used anywhere in this repo. That is a deliberate
  absence, not an oversight: there is no secret to wrap. Should this server ever
  gain a credential, `SecretStr` becomes mandatory, per the MCP Server profile.
- Nothing to scrub from error messages.

**Layer 2 — Input Validation:**
- Source names are resolved and then confirmed to still be inside the log root.
  That catches traversal, absolute paths, and symlinks pointing out of the tree —
  a string check for `..` catches only the first of those.
- Caller-supplied regular expressions are length-capped. Python's `re` has no
  execution timeout, so bounding the input is the available defence.
- Time arguments are parsed strictly and rejected rather than coerced.
- Pydantic models are not used for tool arguments here, because every argument is
  a scalar validated at the point of use (path resolution, regex compilation,
  timestamp parsing) where the check has the context to be meaningful. Pydantic
  remains a dependency and MUST be used if any tool grows a structured argument.

**Layer 3 — API Hardening:**
- There is no outbound API. The equivalent hardening is resource bounding: every
  tool caps both results returned and lines scanned, and reports when either cap
  was hit. Logs are unbounded and the output lands in a context window.
- Time-bounded queries open only the files whose date bucket overlaps the range.

**Layer 4 — Dangerous Operation Prevention:**
- Read-only by construction. No writes, no shell execution, no `eval`/`exec`.
- The log mount MUST be `:ro`. A bug here must not be able to destroy the
  forensic record the server exists to protect.

**Layer 5 — Supply Chain Security:**
- Weekly automated CVE scanning via GitHub Actions.
- Hummingbird container base image (minimal CVE surface).
- Gourmand AI slop detection gating all PRs.

### 2. Two-Layer Tool Architecture

- `server.py` — `@mcp.tool()` functions that validate arguments and delegate
- `tools/*.py` — pure functions over `query.py` / `reader.py`

Never put business logic in `server.py`. Never put MCP registration in `tools/*.py`.

### 3. Three Distribution Channels

| Channel | Command | Use Case |
|---------|---------|----------|
| uvx | `uvx mcp-syslog-crunchtools` | Zero-install, Claude Code |
| pip | `pip install mcp-syslog-crunchtools` | Virtual environments |
| Container | `podman run quay.io/crunchtools/mcp-syslog` | Isolated, systemd |

### 4. Three Transport Modes

`stdio` (default), `sse`, and `streamable-http`. The container runs
`streamable-http` on port 8027 behind the Trentina gateway.

### 5. Honest Results

**A truncated or aborted result MUST say so.** This is a correctness requirement,
not a nicety. The server exists to inform remediation decisions, and a caller that
cannot distinguish "no errors occurred" from "I stopped looking" will act on the
wrong conclusion. `QueryResult` carries `truncated`, `scan_limit_hit` and
`unparsed`, and `render()` surfaces all three.

### 6. Severity Is Reported, Not Interpreted

Podman records anything written to container stderr at syslog priority `err`, so
services logging routine INFO to stderr appear as ERR. The server reports what the
journal says and states the caveat in its MCP instructions. It does not
second-guess severities by inspecting message text — that would be a heuristic
masquerading as data.

Filtering keeps unrecognised severities (hiding a line you do not understand is
worse than showing it), but `syslog_stats_tool` uses a strict lookup when counting
errors. Conflating the two produced a 57% error rate for healthy services against
real logs.

### 7. Semantic Versioning

Semantic Versioning 2.0.0. A change to the parsed log format is MAJOR if it drops
support for a format still inside the collector's retention window.

### 8. AI Code Quality

Gourmand gates all PRs. Comments explain why, not what.

---

## II. Technology Stack

- Python ≥ 3.10, FastMCP ≥ 2.0, Pydantic ≥ 2.0
- No HTTP client dependency — this server reads files
- Standard library only for parsing, reading and gzip decompression
- `uv` for dependency management; `hatchling` for builds
- Licensed AGPL-3.0-or-later, as required by the universal constitution

---

## III. Testing Standards

### Filesystem Fixture Tests (MANDATORY)

Tests build a log root under `tmp_path` and populate it with records in the
collector's format. No live dependency, no network, no access to the real
collector.

### Security Tests (MANDATORY)

`tests/test_security.py` covers path traversal, absolute paths, symlinks escaping
the log root, and regex bounding. These are not optional — they cover the only
genuinely untrusted input this server has.

### Format Compatibility Tests (MANDATORY)

The collector emitted five fields before 2026-08-23 and six after; old lines stay
in retention for 90 days. Both layouts MUST remain covered for as long as
retention outlives the change.

### Honesty Tests

Truncation, scan-limit and unparsed-line reporting MUST be asserted. A silently
truncated result is a correctness bug, not a cosmetic one.

---

## IV. Gourmand (AI Slop Detection)

### Configuration

`gourmand.toml` at the repo root; `gourmand --full .` must report zero violations.

### Exception Policy

Exceptions live in `gourmand-exceptions.toml`, each with a written justification.
An exception is acceptable only when the flagged construct is demonstrably correct
for this repo; it is never a way to silence a finding that is merely inconvenient.

---

## V. Code Quality Gates

Every PR must pass, in order:

1. **Lint** — `uv run ruff check src tests` (zero violations)
2. **Type Check** — `uv run mypy src` (strict mode, zero errors)
3. **Tests** — `uv run pytest -v` (all pass, no live dependencies)
4. **Gourmand** — `gourmand --full .` (zero violations)
5. **Container Build** — `podman build -f Containerfile .`

---

## VI. Naming Conventions

| Context | Pattern | This repo |
|---------|---------|-----------|
| PyPI package | `mcp-<name>-crunchtools` | `mcp-syslog-crunchtools` |
| Python module | `mcp_<name>_crunchtools` | `mcp_syslog_crunchtools` |
| GitHub repo | `crunchtools/mcp-<name>` | `crunchtools/mcp-syslog` |
| Container | `quay.io/crunchtools/mcp-<name>` | `quay.io/crunchtools/mcp-syslog` |
| Tools | `syslog_<verb>_tool` | `syslog_search_tool` |

---

## VII. Development Workflow

### Adding a New Tool

1. Implement the pure function in `tools/<name>.py`
2. Export it from `tools/__init__.py`
3. Register the `@mcp.tool()` wrapper in `server.py` with a full docstring
4. Add fixture-based tests, including any new untrusted-input path
5. Run all five quality gates

### Changing the Log Format

The collector owns the format. A change starts in `crunchtools/syslog`'s
`config/rsyslog.conf` and is mirrored here — never the reverse. Support for the
previous format MUST be retained until it has aged out of retention.

---

## VIII. Governance

### Amendment Process

Amendments are proposed by PR against this file, with the rationale in the PR
body. A version bump here follows Semantic Versioning.

### Ratification History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-08-23 | Initial constitution — RT #1460, Phase 4 |

---

## IX. References

- [crunchtools/constitution](https://github.com/crunchtools/constitution) — universal constitution v1.10.0, Section XIII (Centralized Logging)
- [crunchtools/syslog](https://github.com/crunchtools/syslog) — the collector this server reads
- [crunchtools/mcp-nagios](https://github.com/crunchtools/mcp-nagios) — the alerting half of the same triage loop
- RT #1460 — the ticket this work implements
